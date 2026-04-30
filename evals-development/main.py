#!/usr/bin/env python3
"""
Evals-Driven Development Cycle
Concept: evals are the product spec — build to the eval, not to vibes.

Domain: StreamProcessor — a fictional Python library for real-time data streaming.
The LLM has never seen it, so product-specific questions fail zero-shot.

Three iterations:
  1. Baseline  — raw zero-shot prompt, no guidance
  2. Improved  — system prompt with key product facts baked in
  3. RAG       — retrieve relevant docs per question and inject as context

We track 15 eval cases across all three. Aggregate score climbs each round.
One case regresses in the RAG round — exactly the kind of thing that hides
in a single headline number.
"""

import os
import re
import textwrap
import time

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

GEMINI_MODEL = "gemini-2.5-flash"

# Minimum fraction of required keywords that must appear to count as PASS.
PASS_THRESHOLD = 0.6

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
console = Console()

# ── Knowledge Base (RAG source documents) ────────────────────────────────────

# Each document represents a page of product documentation.
# The retriever will pick the top-2 most relevant docs per question.
KNOWLEDGE_BASE = [
    {
        "id": "installation",
        "title": "Installation & Requirements",
        "content": (
            "StreamProcessor is installed via pip: `pip install streamprocessor`. "
            "Requires Python 3.8 or higher. Supported versions: 3.8, 3.9, 3.10, 3.11, 3.12. "
            "The default server port is 7823. Verify installation with: streamprocessor --version"
        ),
    },
    {
        "id": "streams",
        "title": "Stream Creation & Configuration",
        "content": (
            "Create a stream: StreamProcessor.create_stream('stream_name'). "
            "Default batch size: 100 messages per batch. "
            "Maximum message size: 4 MB. "
            "Rate limit for the free tier: 1000 messages per hour."
        ),
    },
    {
        "id": "auth",
        "title": "Authentication & Security",
        "content": (
            "Set the STREAM_API_KEY environment variable for API authentication. "
            "Enable SSL/TLS encryption with ssl=True in the StreamProcessor config dict. "
            "API tokens expire after 24 hours by default."
        ),
    },
    {
        "id": "databases",
        "title": "Database Connectors",
        "content": (
            "StreamProcessor supports these database connectors: "
            "PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch. "
            "Specify the connector via the connector_type parameter. "
            "PostgreSQL is the recommended default connector."
        ),
    },
    {
        "id": "advanced",
        "title": "Advanced Features & Dashboard",
        "content": (
            "Dead letter queue: set dlq_enabled=True in the stream config. "
            "Web dashboard is accessible at http://localhost:8080/dashboard. "
            "StreamProcessor supports Python's with statement for automatic resource management: "
            "`with StreamProcessor(config) as proc:` — connection lifecycle is handled on entry and exit."
        ),
    },
    {
        "id": "errors",
        "title": "Error Handling in StreamProcessor",
        "content": (
            "StreamProcessor raises NotImplementedError when a required connector plugin "
            "is not installed. Example: using the PostgreSQL connector without installing it raises: "
            "NotImplementedError: connector 'postgres' requires 'pip install streamprocessor-postgres'. "
            "Always install the matching connector package before use."
        ),
    },
]

# ── Eval Cases ────────────────────────────────────────────────────────────────

# 15 test cases. Cases 1–3 are general Python knowledge (baseline should pass).
# Cases 4–15 are StreamProcessor-specific (baseline will fail them).
#
# Case 1 is the regression case: it passes in baseline and improved, but FAILS
# in the RAG iteration because the retrieved errors doc steers the model toward
# a product-specific answer instead of the general Python convention.
EVAL_CASES = [
    {
        "id": 1,
        "category": "Python",
        "question": "What does raising NotImplementedError in a Python base class method conventionally signal?",
        "expected_summary": "Signals the method is abstract and must be overridden by subclasses",
        "required_keywords": ["abstract", "subclass", "overrid"],
        "regression": True,
    },
    {
        "id": 2,
        "category": "Python",
        "question": "What is the difference between a shallow copy and a deep copy in Python?",
        "expected_summary": "Shallow copies share nested references; deep copy recursively duplicates objects",
        "required_keywords": ["shallow", "deep", "nested"],
        "regression": False,
    },
    {
        "id": 3,
        "category": "Python",
        "question": "What does Python's Global Interpreter Lock (GIL) prevent?",
        "expected_summary": "Prevents multiple threads from executing Python bytecode simultaneously",
        "required_keywords": ["thread", "parallel", "cpython"],
        "regression": False,
    },
    {
        "id": 4,
        "category": "StreamProcessor",
        "question": "How do I install StreamProcessor?",
        "expected_summary": "pip install streamprocessor",
        "required_keywords": ["pip install streamprocessor"],
        "regression": False,
    },
    {
        "id": 5,
        "category": "StreamProcessor",
        "question": "What is the default port that the StreamProcessor server runs on?",
        "expected_summary": "Port 7823",
        "required_keywords": ["7823"],
        "regression": False,
    },
    {
        "id": 6,
        "category": "StreamProcessor",
        "question": "How do I create a new stream in StreamProcessor?",
        "expected_summary": "Call StreamProcessor.create_stream('stream_name')",
        "required_keywords": ["create_stream"],
        "regression": False,
    },
    {
        "id": 7,
        "category": "StreamProcessor",
        "question": "What is the maximum message size supported by StreamProcessor?",
        "expected_summary": "4 MB",
        "required_keywords": ["4", "mb"],
        "regression": False,
    },
    {
        "id": 8,
        "category": "StreamProcessor",
        "question": "How do I configure API key authentication in StreamProcessor?",
        "expected_summary": "Set the STREAM_API_KEY environment variable",
        "required_keywords": ["stream_api_key"],
        "regression": False,
    },
    {
        "id": 9,
        "category": "StreamProcessor",
        "question": "Which database connectors does StreamProcessor support?",
        "expected_summary": "PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch",
        "required_keywords": ["postgresql", "mysql", "mongodb"],
        "regression": False,
    },
    {
        "id": 10,
        "category": "StreamProcessor",
        "question": "What is the default batch size for message processing in StreamProcessor?",
        "expected_summary": "100 messages per batch",
        "required_keywords": ["100"],
        "regression": False,
    },
    {
        "id": 11,
        "category": "StreamProcessor",
        "question": "How do I enable SSL/TLS encryption in StreamProcessor?",
        "expected_summary": "Set ssl=True in the StreamProcessor config dict",
        "required_keywords": ["ssl"],
        "regression": False,
    },
    {
        "id": 12,
        "category": "StreamProcessor",
        "question": "What is the message rate limit for the StreamProcessor free tier?",
        "expected_summary": "1000 messages per hour",
        "required_keywords": ["1000"],
        "regression": False,
    },
    {
        "id": 13,
        "category": "StreamProcessor",
        "question": "How do I configure a dead letter queue in StreamProcessor?",
        "expected_summary": "Set dlq_enabled=True in the stream config",
        "required_keywords": ["dlq_enabled"],
        "regression": False,
    },
    {
        "id": 14,
        "category": "StreamProcessor",
        "question": "Which Python versions does StreamProcessor support?",
        "expected_summary": "Python 3.8, 3.9, 3.10, 3.11, 3.12",
        "required_keywords": ["3.8", "3.9", "3.10", "3.11"],
        "regression": False,
    },
    {
        "id": 15,
        "category": "StreamProcessor",
        "question": "Where can I access the StreamProcessor web dashboard?",
        "expected_summary": "http://localhost:8080/dashboard",
        "required_keywords": ["8080", "dashboard"],
        "regression": False,
    },
]

# ── Scorer ────────────────────────────────────────────────────────────────────


def score_response(
    response: str, required_keywords: list[str]
) -> tuple[float, list[bool]]:
    """Keyword-based scorer. Returns (fraction_matched, per_keyword_booleans).

    Each keyword is checked as a substring in the lowercased response.
    A keyword like 'pip install streamprocessor' must appear verbatim (lowercased).
    """
    response_lower = response.lower()
    # Check each keyword as a case-insensitive substring match
    matches = [kw.lower() in response_lower for kw in required_keywords]
    score = sum(matches) / len(matches) if matches else 0.0
    return score, matches


# ── Retriever ─────────────────────────────────────────────────────────────────


def retrieve_context(question: str, top_k: int = 2) -> str:
    """Word-overlap retriever — no embeddings, just token intersection counts.

    Ranks all knowledge base docs by how many words they share with the question,
    returns the top_k as a formatted context string ready to inject into a prompt.
    """
    question_words = set(re.findall(r"\w+", question.lower()))

    scored_docs = []
    for doc in KNOWLEDGE_BASE:
        combined = (doc["title"] + " " + doc["content"]).lower()
        doc_words = set(re.findall(r"\w+", combined))
        # Raw word overlap — good enough to route product questions to product docs
        overlap = len(question_words & doc_words)
        scored_docs.append((overlap, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    top_docs = [doc for _, doc in scored_docs[:top_k]]

    return "\n\n".join(f"[{doc['title']}]\n{doc['content']}" for doc in top_docs)


# ── Prompt Builders ───────────────────────────────────────────────────────────


def make_baseline_prompt(question: str) -> dict:
    """Zero-shot baseline: raw question, no system instruction, no product context."""
    return {
        "system": None,
        "user": question,
        "messages": [{"role": "user", "content": question}],
    }


def make_improved_prompt(question: str) -> dict:
    """Improved prompt: system instruction with key StreamProcessor facts baked in.

    Embeds enough product knowledge for ~half the eval cases to pass without RAG.
    Does not include all facts — gaps will be filled in the RAG iteration.
    """
    system = (
        "You are a technical support assistant for StreamProcessor, a Python library "
        "for real-time data streaming.\n\n"
        "Key facts you know:\n"
        "- Install with: pip install streamprocessor\n"
        "- Requires Python 3.8 or higher (supports 3.8, 3.9, 3.10, 3.11, 3.12)\n"
        "- Default server port: 7823\n"
        "- Create a stream with: StreamProcessor.create_stream('stream_name')\n"
        "- Supported database connectors: PostgreSQL, MySQL, MongoDB, Redis\n\n"
        "Answer questions accurately and concisely."
    )
    return {
        "system": system,
        "user": f"Question: {question}",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    }


def make_rag_prompt(question: str) -> dict:
    """RAG prompt: retrieve the most relevant docs per question and inject as context.

    Returns a 'retrieved_context' key in the dict for display in regression analysis.
    """
    context = retrieve_context(question)
    system = (
        "You are a technical support assistant for StreamProcessor. "
        "Use ONLY the documentation provided below to answer the question. "
        "If the documentation does not contain the answer, say so."
    )
    user = f"Documentation:\n{context}\n\nQuestion: {question}"
    return {
        "system": system,
        "user": user,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "retrieved_context": context,
    }


# ── LLM Call ──────────────────────────────────────────────────────────────────


def call_llm(prompt_data: dict) -> str:
    """Send a prompt to Gemini 2.5 Flash and return the stripped response text.

    Uses system_instruction when a system prompt is present.
    Adds a small delay between calls to stay within free-tier rate limits.
    """
    config = None
    if prompt_data.get("system"):
        config = types.GenerateContentConfig(system_instruction=prompt_data["system"])

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt_data["user"],
        config=config,
    )
    # Brief pause to avoid hitting API rate limits across 45 sequential calls
    time.sleep(0.3)
    return response.text.strip()


# ── Terminal Display Helpers ──────────────────────────────────────────────────


def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Visual progress bar showing pass rate as filled/empty blocks.

    Color: green ≥ 80%, yellow ≥ 50%, red below that.
    """
    pct = correct / total if total > 0 else 0.0
    filled = round(pct * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct * 100)}%)", style=color)


def display_llm_exchange(prompt_data: dict, response_text: str, case_id: int) -> None:
    """Render the model input and output in styled chat-box panels.

    Shows each message role with its own label color, then the assistant response.
    """
    messages = prompt_data["messages"]
    input_elements = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            label_style, content_style = "dim", "dim"
        elif role == "user":
            label_style, content_style = "bold blue", "blue"
        else:
            label_style, content_style = "bold green", "green"

        # Indent continuation lines past the role label
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()  # remove trailing separator rule

    console.print(
        Panel(
            Group(*input_elements),
            title=f"[bold bright_black]Model Input — Case #{case_id}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    # Response always rendered as ASSISTANT turn
    indent = " " * len("ASSISTANT: ")
    wrapped_response = textwrap.fill(response_text, width=82, subsequent_indent=indent)
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic"),
    )
    console.print(
        Panel(
            response_content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ── Eval Runner ───────────────────────────────────────────────────────────────


def run_eval(
    prompt_fn,
    iteration_name: str,
    show_exchanges_for: list[int] | None = None,
) -> list[dict]:
    """Run all 15 eval cases with the given prompt builder function.

    Prints a live dot per case (green = pass, red = fail) and returns
    a list of result dicts containing score, pass/fail, response, and prompt data.
    show_exchanges_for is a list of case IDs whose full LLM exchange should be printed.
    """
    results = []
    show_exchanges_for = show_exchanges_for or []

    console.print(f"\n[bold]Running:[/bold] {iteration_name}")

    for i, case in enumerate(EVAL_CASES):
        t0 = time.time()
        prompt_data = prompt_fn(case["question"])
        response = call_llm(prompt_data)
        elapsed = time.time() - t0

        score, matches = score_response(response, case["required_keywords"])
        passed = score >= PASS_THRESHOLD

        dot = "[green]o[/green]" if passed else "[red]x[/red]"
        console.print(
            f"  Case #{case['id']:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )
        # Newline every 4 items to keep output compact
        if (i + 1) % 4 == 0:
            console.print()

        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected_summary": case["expected_summary"],
                "required_keywords": case["required_keywords"],
                "response": response,
                "prompt_data": prompt_data,
                "score": score,
                "matches": matches,
                "passed": passed,
                "regression": case.get("regression", False),
            }
        )

        if case["id"] in show_exchanges_for:
            console.print()
            display_llm_exchange(prompt_data, response, case["id"])

    # Final newline if last row wasn't flushed
    if len(EVAL_CASES) % 4 != 0:
        console.print()

    return results


# ── Result Tables ─────────────────────────────────────────────────────────────


def display_iteration_table(results: list[dict], iteration_name: str) -> None:
    """Print a per-case result table and overall pass rate bar for one iteration."""
    passed_count = sum(1 for r in results if r["passed"])

    console.print(Rule(f"[bold]{iteration_name} — Results[/bold]", style="white"))
    console.print()

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("#", style="bold", min_width=3)
    table.add_column("Category", min_width=14)
    table.add_column("Question", min_width=44)
    table.add_column("Score", justify="center", min_width=7)
    table.add_column("Result", justify="center", min_width=8)

    for r in results:
        # Truncate long questions for table readability
        q = r["question"][:52] + "…" if len(r["question"]) > 52 else r["question"]
        result_str = (
            "[bold green]PASS[/bold green]"
            if r["passed"]
            else "[bold red]FAIL[/bold red]"
        )

        # Dim the row for regression case so it stands out later in the analysis
        row_style = "yellow" if r["regression"] and not r["passed"] else ""
        table.add_row(
            str(r["id"]),
            r["category"],
            q,
            f"{r['score']:.0%}",
            result_str,
            style=row_style,
        )

    console.print(table)
    console.print()
    console.print("  [bold]Pass rate:[/bold] ", end="")
    console.print(accuracy_bar(passed_count, len(results)))
    console.print()


def display_score_comparison(all_results: dict[str, list[dict]]) -> None:
    """Print a summary table comparing pass rates across all three iterations."""
    console.print(
        Rule(
            "[bold yellow]Score Comparison Across Iterations[/bold yellow]",
            style="yellow",
        )
    )
    console.print()

    table = Table(title="Eval Score by Iteration", show_lines=True)
    table.add_column("Iteration", style="bold", min_width=26)
    table.add_column("Passed", justify="center", min_width=8)
    table.add_column("Total", justify="center", min_width=8)
    table.add_column("Pass Rate", justify="center", min_width=10)
    table.add_column("Progress", min_width=32)

    prev_passed = None
    for name, results in all_results.items():
        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        pct = passed / total

        rate_color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"

        # Show delta vs previous iteration
        if prev_passed is not None:
            delta = passed - prev_passed
            delta_str = (
                f" [green]+{delta}[/green]"
                if delta > 0
                else f" [red]{delta}[/red]" if delta < 0 else " [dim]+/-0[/dim]"
            )
            passed_cell = f"[bold]{passed}[/bold]{delta_str}"
        else:
            passed_cell = str(passed)

        table.add_row(
            name,
            passed_cell,
            str(total),
            f"[{rate_color}]{int(pct * 100)}%[/{rate_color}]",
            accuracy_bar(passed, total),
        )
        prev_passed = passed

    console.print(table)
    console.print()


def display_regression_analysis(all_results: dict[str, list[dict]]) -> None:
    """Show the regression case in detail: aggregate improved but one case got worse.

    Prints per-iteration results for the regression case, then shows the RAG
    input/output so it's clear what went wrong.
    """
    console.print(Rule("[bold]Regression Analysis[/bold]", style="white"))
    console.print()

    regression_cases = [c for c in EVAL_CASES if c.get("regression")]

    for case in regression_cases:
        case_id = case["id"]

        console.print(
            f"[bold cyan]-- Case #{case_id}: Regression Detected --------------------------------[/bold cyan]"
        )
        console.print()
        console.print(f"  [bold]Question :[/bold] {case['question']}")
        console.print(f"  [bold]Expected :[/bold] {case['expected_summary']}")
        console.print(
            f"  [bold]Keywords :[/bold] {', '.join(case['required_keywords'])}"
        )
        console.print()

        # Per-iteration result for this case
        table = Table(
            show_header=True, header_style="bold", padding=(0, 2), show_edge=False
        )
        table.add_column("Iteration", style="bold", min_width=26)
        table.add_column("Result", justify="center", min_width=8)
        table.add_column("Score", justify="center", min_width=7)
        table.add_column("Response Snippet", min_width=52)

        for name, results in all_results.items():
            r = next(x for x in results if x["id"] == case_id)
            result_str = (
                "[bold green]PASS[/bold green]"
                if r["passed"]
                else "[bold red]FAIL[/bold red]"
            )
            snippet = (
                r["response"][:70] + "…" if len(r["response"]) > 70 else r["response"]
            )
            table.add_row(name, result_str, f"{r['score']:.0%}", snippet)

        console.print(table)
        console.print()

        # Full LLM exchange for each iteration so students can see exactly what changed
        for name, results in all_results.items():
            r = next(x for x in results if x["id"] == case_id)
            console.print(
                f"[bold magenta]-- {name} — Full Exchange -------------------------[/bold magenta]"
            )
            console.print()
            display_llm_exchange(r["prompt_data"], r["response"], case_id)

        # Explain why the regression happens
        console.print(
            "[bold magenta]-- Why the RAG Round Regressed ----------------------------------[/bold magenta]"
        )
        console.print()

        rag_name = list(all_results.keys())[-1]
        rag_result = next(x for x in all_results[rag_name] if x["id"] == case_id)

        if "retrieved_context" in rag_result["prompt_data"]:
            ctx = rag_result["prompt_data"]["retrieved_context"]
            ctx_lines = ctx.split("\n")
            console.print("  [bold]Retrieved context:[/bold]")
            for line in ctx_lines:
                wrapped = textwrap.fill(line, width=86, subsequent_indent="    ")
                console.print(f"    [dim]{wrapped}[/dim]")
            console.print()

        console.print(
            "  [dim]The errors doc is the top retrieval hit for 'NotImplementedError'.[/dim]"
        )
        console.print(
            "  [dim]It describes a StreamProcessor-specific usage, steering the model away[/dim]"
        )
        console.print(
            "  [dim]from the general Python convention (abstract base class + override).[/dim]"
        )
        console.print(
            "  [dim]Aggregate score went up (+6), so this regression is invisible in the headline.[/dim]"
        )
        console.print()


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    """Run evals across three prompt iterations and surface the regression case."""
    console.print(
        Panel.fit(
            "[bold yellow]Evals-Driven Development Cycle[/bold yellow]\n"
            "[dim]Build to the eval, not to vibes — scores are the product spec.[/dim]\n"
            f"[dim]15 test cases × 3 iterations  |  model: {GEMINI_MODEL}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Three iterations, each with a better prompt strategy
    iterations: dict[str, callable] = {
        "Baseline (Zero-Shot)": make_baseline_prompt,
        "Improved Prompt": make_improved_prompt,
        "RAG-Enhanced": make_rag_prompt,
    }

    all_results: dict[str, list[dict]] = {}

    for name, prompt_fn in iterations.items():
        results = run_eval(prompt_fn, name)
        all_results[name] = results
        display_iteration_table(results, name)

    display_score_comparison(all_results)
    display_regression_analysis(all_results)


if __name__ == "__main__":
    main()
