import os

from google import genai
from google.genai import types

from models import Workflow

# The model that powers the NL → DAG conversion step.
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# System prompt that teaches Gemini how to produce a valid DAG from free-form text.
# Kept at module level so it can be shared / inspected during a walkthrough.
PARSER_SYSTEM_PROMPT = """You are a workflow compiler. Your job is to parse a plain-English
workflow description and emit a structured Directed Acyclic Graph (DAG).

Rules for building the DAG
--------------------------
1. Every distinct step in the description becomes exactly one node.
2. A node's `depends_on` list must contain the IDs of every node whose output it needs.
3. Steps that do NOT share a data dependency must NOT be linked — they will run in parallel.
4. Use snake_case for all node IDs (e.g. fetch_hn_posts, summarize_articles).
5. Populate `params` with anything concrete mentioned in the description:
   - fetch  → url (if given) or data_source (e.g. "hacker_news", "github_trending")
   - translate → target_language
   - email   → recipient (use "user" if not specified)
   - others  → any relevant key/value pairs

Node types and when to use them
--------------------------------
- fetch     : retrieve data from an external source (API, URL, RSS, etc.)
- summarize : condense content into a shorter form
- translate : convert text from one language to another
- email     : send the final output to a recipient
- transform : reshape or reformat data without changing its language
- filter    : keep only items matching certain criteria
- aggregate : merge outputs from multiple upstream nodes into one

Parallelism example
-------------------
Description: "Fetch weather and news, summarise both, merge into a report, email it"
Correct DAG:
  fetch_weather  (fetch,     depends_on: [])
  fetch_news     (fetch,     depends_on: [])
  summarize_weather (summarize, depends_on: [fetch_weather])
  summarize_news    (summarize, depends_on: [fetch_news])
  merge_report   (aggregate, depends_on: [summarize_weather, summarize_news])
  email_report   (email,     depends_on: [merge_report])

fetch_weather and fetch_news have no dependency on each other → they run in parallel.
"""


def parse_workflow(description: str, client: genai.Client) -> tuple[Workflow, str]:
    """Parses a natural language description into a structured Workflow DAG.

    Uses Gemini's structured output capability to ensure the response adheres
    exactly to the Workflow Pydantic model. Sets a low temperature for
    deterministic structure generation. Returns a tuple of (Workflow, raw_json).
    """
    # use structured-output mode to avoid manual parsing or regex
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Parse this workflow into a DAG:\n\n{description}",
        config=types.GenerateContentConfig(
            system_instruction=PARSER_SYSTEM_PROMPT,
            # enforce JSON schema matching the Pydantic model
            response_mime_type="application/json",
            response_schema=Workflow,
            temperature=0.1,
        ),
    )
    # validate and instantiate the Pydantic model from JSON
    return Workflow.model_validate_json(response.text), response.text
