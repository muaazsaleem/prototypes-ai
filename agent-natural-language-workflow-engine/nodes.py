import os
from typing import AsyncGenerator

import httpx
from google import genai
from google.genai import types

from cache import PromptCacheManager
from models import NodeType, WorkflowNode

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Shared system prompt used by every LLM node.
# It is long enough (>1 024 tokens) to qualify for Gemini context caching,
# so all LLM nodes in a single run share one cached upload.
# ---------------------------------------------------------------------------
WORKFLOW_SYSTEM_PROMPT = """
You are an intelligent step executor inside an automated workflow engine.
Your job is to process the input data passed to you and produce well-formatted
output that will be consumed by the next step in the pipeline.

Since you are running inside an automated system with no human in the loop,
accuracy and completeness are critical.  Do not hallucinate.  Do not add
information that is not present in the input you are given.

Start your response with useful content immediately — no preambles like
"Sure, here is …" or "I will now …".  The workflow engine streams your tokens
directly to the user, so every token should carry value.

=== SUMMARIZE ===
When the operation is "summarize":
- Extract the 3–6 most important facts or insights from the input.
- Start with the single most important point.
- Use bullet points ( - ) for lists of items.
- Preserve numbers, dates, proper nouns, URLs, and technical terms exactly as given.
- For news items: cover what happened, who is involved, and why it matters.
- For technical posts or papers: cover the problem, approach, and key outcome.
- For repository listings: cover the project name, what it does, and its
  headline metric (stars, language, recent activity).
- Target length: 20–30 % of the input length.
- Do NOT include commentary such as "In summary" or "To summarise".

=== TRANSLATE ===
When the operation is "translate":
- Produce natural, idiomatic translations — not word-for-word.
- Preserve all formatting: bullet points stay bullet points, headers stay headers,
  bold stays bold.
- For Spanish (es): use the formal register (usted) unless the source is clearly
  casual or conversational.
- For French (fr): use formal "vous" unless the source is clearly informal.
- For technical terms with no standard translation in the target language:
  keep the English term and add a brief parenthetical explanation.
- Leave all URLs, email addresses, numbers, and code snippets untranslated.
- Do not add translator notes unless the text is genuinely ambiguous.

=== AGGREGATE ===
When the operation is "aggregate":
- Merge all inputs into one coherent document.
- Use clear ## section headers to separate content from different upstream nodes.
- Eliminate exact duplicates but do NOT omit unique facts.
- Highlight connections or patterns that appear across multiple inputs.
- Do not editorialize or add opinions not present in the source material.

=== TRANSFORM ===
When the operation is "transform":
- Follow the transformation specification in the node params exactly.
- Preserve all information unless the spec explicitly says to discard it.
- If the transformation spec is ambiguous, apply your best judgment and note
  the assumption in a single parenthetical comment at the top of the output.

=== FILTER ===
When the operation is "filter":
- Apply the filter criteria precisely as specified in params.
- If nothing passes the filter, return an explicit empty-result message such as
  "No items matched the filter criteria."
- Do not silently drop items; briefly note what was removed when that is useful.

=== OUTPUT FORMAT ===
- Always output valid Markdown.
- Use ## for top-level sections, ### for sub-sections.
- Bold (**text**) for emphasis; never ALL CAPS for emphasis.
- Use - bullets (not numbers) unless order matters.
- Wrap code, URLs, and identifiers in backticks.
- End output with a single blank line; no trailing commentary.

=== OPERATIONAL CONTEXT ===
You are running inside an async DAG executor.  Independent nodes run in
parallel, so your output may be consumed by multiple downstream nodes
simultaneously.  Nodes that share this system prompt reuse a Gemini context
cache — you are reading from that cache right now.  Your input will arrive
in a structured block that lists the node id, operation type, description,
params, and the concatenated outputs of all upstream nodes.
"""


# ---------------------------------------------------------------------------
# Public dispatch function
# ---------------------------------------------------------------------------


async def run_node(
    node: WorkflowNode,
    inputs: dict[str, str],
    client: genai.Client,
    cache_manager: PromptCacheManager,
) -> AsyncGenerator[str, None]:
    """Routes execution to the appropriate handler and yields output chunks.

    Dispatches to local fetch/email runners or to Gemini for LLM-powered
    operations. Yields string chunks to support real-time streaming in the CLI.
    """
    if node.type == NodeType.FETCH:
        async for chunk in _run_fetch(node, inputs):
            yield chunk
    elif node.type == NodeType.EMAIL:
        async for chunk in _run_email(node, inputs):
            yield chunk
    else:
        # summarize / translate / transform / filter / aggregate → Gemini
        async for chunk in _run_llm(node, inputs, client, cache_manager):
            yield chunk


# ---------------------------------------------------------------------------
# Fetch node  — pulls data from external APIs
# ---------------------------------------------------------------------------


async def _run_fetch(
    node: WorkflowNode, inputs: dict[str, str]
) -> AsyncGenerator[str, None]:
    """Retrieves data from external sources based on node parameters.

    Supports pre-defined sources like Hacker News and GitHub, direct URLs,
    or falls back to mock data if no source is specified.
    """
    source = node.params.get("data_source", "").lower()
    url = node.params.get("url", "")

    async with httpx.AsyncClient(timeout=15) as http:
        if "hacker_news" in source or "hackernews" in source or "hn" in source:
            yield await _fetch_hacker_news(http, node.params.get("limit", 10))

        elif "github" in source:
            yield await _fetch_github_trending(http, node.params.get("limit", 5))

        elif url:
            resp = await http.get(url)
            resp.raise_for_status()
            # truncate large responses to avoid overwhelming context limits
            yield resp.text[:6000]

        else:
            # graceful fallback for demo scenarios
            yield (
                f"[fetch node '{node.id}': no data_source or url in params]\n"
                f"Mock data for: {node.description}"
            )


async def _fetch_hacker_news(http: httpx.AsyncClient, limit: int) -> str:
    """Fetches top Hacker News stories and returns them as a Markdown list.

    Iterates through story IDs and fetches details for each story. Returns
    a formatted string with titles, links, and scores.
    """
    resp = await http.get("https://hacker-news.firebaseio.com/v0/topstories.json")
    resp.raise_for_status()
    ids = resp.json()[:limit]

    lines = []
    for story_id in ids:
        r = await http.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        )
        item = r.json()
        title = item.get("title", "No title")
        link = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        score = item.get("score", 0)
        lines.append(f"- [{title}]({link}) | score: {score}")

    return "\n".join(lines)


async def _fetch_github_trending(http: httpx.AsyncClient, limit: int) -> str:
    """Queries GitHub for top-starred repositories as a proxy for trending.

    Uses the search API to find repos with high star counts. Returns a
    Markdown bullet list with repository metadata.
    """
    resp = await http.get(
        "https://api.github.com/search/repositories",
        params={
            "q": "stars:>5000",
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
        headers={"Accept": "application/vnd.github+json"},
    )
    resp.raise_for_status()
    repos = resp.json().get("items", [])[:limit]

    lines = []
    for repo in repos:
        name = repo["full_name"]
        desc = repo.get("description") or "No description"
        stars = repo.get("stargazers_count", 0)
        lang = repo.get("language") or "unknown"
        lines.append(
            f"- [{name}](https://github.com/{name}) — {desc} | ⭐ {stars} | {lang}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email node  — simulated (prints to console in a demo context)
# ---------------------------------------------------------------------------


async def _run_email(
    node: WorkflowNode, inputs: dict[str, str]
) -> AsyncGenerator[str, None]:
    """Generates a Markdown preview of an email without actually sending it.

    Combines all upstream inputs into the email body and uses parameters
    for the recipient and subject lines.
    """
    recipient = node.params.get("recipient", "user@example.com")
    subject = node.params.get("subject", "Workflow Digest")
    body = "\n\n".join(inputs.values()) if inputs else "(no content)"

    yield (
        f"📧 **[Email simulated — not actually sent]**\n\n"
        f"**To:** {recipient}  \n"
        f"**Subject:** {subject}  \n\n"
        f"---\n\n{body}"
    )


# ---------------------------------------------------------------------------
# LLM node  — all AI-powered operations (summarize, translate, aggregate …)
# ---------------------------------------------------------------------------


async def _run_llm(
    node: WorkflowNode,
    inputs: dict[str, str],
    client: genai.Client,
    cache_manager: PromptCacheManager,
) -> AsyncGenerator[str, None]:
    """Streams a response from Gemini for AI-driven workflow operations.

    Constructs a detailed prompt containing node metadata and upstream data,
    then uses context caching if available to execute the operation.
    """

    # assemble the input data block from all dependent nodes
    input_block = (
        "\n\n".join(f"### Input from [{dep}]\n{text}" for dep, text in inputs.items())
        if inputs
        else "(no upstream input)"
    )

    user_message = f"""\
Node id:     {node.id}
Operation:   {node.type.value}
Description: {node.description}
Params:      {node.params}

--- INPUT DATA ---
{input_block}
--- END INPUT ---

Execute the operation described above on the input data.
"""

    # retrieve or create a cached system prompt to save tokens
    cache_name = cache_manager.get_or_create(WORKFLOW_SYSTEM_PROMPT)

    if cache_name:
        config = types.GenerateContentConfig(
            cached_content=cache_name,
            temperature=0.7,
        )
    else:
        config = types.GenerateContentConfig(
            system_instruction=WORKFLOW_SYSTEM_PROMPT,
            temperature=0.7,
        )

    # stream the response chunks to keep the UI responsive
    async for chunk in client.aio.models.generate_content_stream(
        model=MODEL,
        contents=user_message,
        config=config,
    ):
        if chunk.text:
            yield chunk.text
