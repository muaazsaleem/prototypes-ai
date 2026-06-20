#!/usr/bin/env python3
"""
Prompt Regression Harness
=========================
Concept: Prompts are code. They need tests. Changes have consequences.

This harness:
  1. Defines two versions of a prompt (v1 = baseline, v2 = "improved")
  2. Runs 10 test cases against each version
  3. Shows a pass/fail comparison table that highlights regressions and fixes
"""

import json
import os
import time
import textwrap

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ─── Prompt Versions ──────────────────────────────────────────────────────────
#
# Both prompts classify a customer support message into urgency + category.
#
# v2 adds one "reasonable-sounding" rule — watch which tests break.

PROMPT_V1 = textwrap.dedent("""\
    You are a customer support triage assistant.
    Classify the incoming customer message and return ONLY valid JSON.
    No markdown, no explanation — raw JSON only.

    Output format:
      {"urgency": "LOW|MEDIUM|HIGH", "category": "billing|technical|general"}

    Rules:
    - Urgency levels:
      HIGH   — service outage, data loss, security breach, active revenue loss, or urgent log in issues.
      MEDIUM — degraded experience, partial failure, time-sensitive non-critical request, or refunds / payment renewal cancellations.
      LOW    — general questions, billing documentation, API keys/documentation for personal use, feature requests, password reset settings, or compliments.

    - Categories:
      billing   — charges, payments, invoices, refunds, or subscription changes.
      technical — product bugs, errors, performance problems, API tokens, API documentation, or technical setup instructions.
      general   — general configuration questions, settings (like profile picture, changing/updating password settings), and other non-billing non-technical requests.
""")

PROMPT_V2 = textwrap.dedent("""\
    You are a customer support triage assistant.
    Classify the incoming customer message and return ONLY valid JSON.
    No markdown, no explanation — raw JSON only.

    Output format:
      {"urgency": "LOW|MEDIUM|HIGH", "category": "billing|technical|general"}

    Urgency levels:
      HIGH   — service outage, data loss, security breach, or active revenue loss
      MEDIUM — degraded experience, partial failure, time-sensitive non-critical request
      LOW    — general questions, feature requests, or compliments

    Categories:
      billing   — charges, payments, invoices, refunds, or subscription changes
      technical — product bugs, errors, performance problems
      general   — everything else

    Additional rule: To improve security and developer support, any message
    mentioning 'API', 'token', 'webhook', 'password', or 'login' MUST be
    classified as HIGH urgency and 'technical', regardless of the context.

    In addition to the above, requests for copies of invoices for accounting should be treated as MEDIUM urgency.
""")

# ─── Test Suite ───────────────────────────────────────────────────────────────
#
# 10 test cases covering all urgency levels and categories.
# expected = the ground-truth label we want the prompt to produce every time.

TEST_CASES = [
    {
        "id": 1,
        "input": "My entire team cannot log in since this morning. We have a client deadline today.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 2,
        "input": "How do I change my profile picture?",
        "expected": {"urgency": "LOW", "category": "general"},
    },
    {
        "id": 3,
        "input": "I need a copy of my invoice from last month for my accounting team.",
        "expected": {"urgency": "LOW", "category": "billing"},
    },
    {
        "id": 4,
        "input": "Where can I find the API token for my personal hobby project?",
        "expected": {"urgency": "LOW", "category": "technical"},
    },
    {
        "id": 5,
        "input": "I'm getting 500 errors on the checkout page and losing sales right now.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 6,
        "input": "Can you send me the link to your REST API documentation?",
        "expected": {"urgency": "LOW", "category": "technical"},
    },
    {
        "id": 7,
        "input": "The mobile app is noticeably slow when scrolling through my feed.",
        "expected": {"urgency": "MEDIUM", "category": "technical"},
    },
    {
        "id": 8,
        "input": "I'd like to update my password for security, where is the setting?",
        "expected": {"urgency": "LOW", "category": "general"},
    },
    {
        "id": 9,
        "input": "I found a critical bug where webhook validation can be bypassed.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 10,
        "input": "Can I get a refund for my recent payment? I didn't mean to renew.",
        "expected": {"urgency": "MEDIUM", "category": "billing"},
    },
]

# ─── Display Helpers ──────────────────────────────────────────────────────────


def display_model_input(system_prompt: str, user_message: str):
    """Styles and prints the system prompt and user message in a grey panel."""
    input_elements = []

    # System prompt
    wrapped_sys = textwrap.fill(system_prompt, width=82, subsequent_indent="        ")
    input_elements.append(Text.assemble(("SYSTEM: ", "dim"), (wrapped_sys, "dim")))
    input_elements.append(Rule(style="bright_black"))

    # User message
    wrapped_user = textwrap.fill(user_message, width=82, subsequent_indent="      ")
    input_elements.append(
        Text.assemble(("USER: ", "bold blue"), (wrapped_user, "blue"))
    )

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_model_output(response_text: str):
    """Styles and prints the model response in a grey panel."""
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
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


# ─── Core Harness ─────────────────────────────────────────────────────────────


def classify(client: genai.Client, prompt: str, message: str) -> dict:
    """Calls the Gemini model with a structured prompt and parses the JSON response.

    Strips any markdown code fences the model might wrap the JSON in before parsing.
    Returns an empty dict if the JSON is invalid.
    """
    full_prompt = f"{prompt}\nCustomer message:\n{message}"
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
    )
    text = response.text.strip()

    # Strip markdown code fences the model sometimes adds around JSON blocks
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def check(actual: dict, expected: dict) -> tuple[bool, str]:
    """Compares the actual model output against expected ground truth fields.

    Returns a tuple of (passed, failure_reason).
    """
    for field in ("urgency", "category"):
        if actual.get(field) != expected[field]:
            return (
                False,
                f"{field}: expected '{expected[field]}', got '{actual.get(field)}'",
            )
    return True, ""


def run_suite(client: genai.Client, prompt: str, label: str, color: str) -> list[dict]:
    """Executes the full test suite against a specific prompt version.

    Uses live progress dots for visual feedback during execution.
    Returns a list of test execution results.
    """
    console.print(
        f"[bold {color}]-- {label} --------------------------------------[/bold {color}]"
    )
    results = []

    for i, tc in enumerate(TEST_CASES, start=1):
        start_time = time.time()
        try:
            actual = classify(client, prompt, tc["input"])
            passed, reason = check(actual, tc["expected"])
        except Exception as exc:
            actual = {}
            passed, reason = False, f"exception: {exc}"

        elapsed = time.time() - start_time

        # Render visual progress dots per item
        dot = "[green]o[/green]" if passed else "[red]o[/red]"
        console.print(
            f"  Item #{tc['id']:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )

        # Break line every 4 items to keep the terminal compact
        if i % 4 == 0:
            console.print()

        results.append(
            {
                "id": tc["id"],
                "input": tc["input"],
                "expected": tc["expected"],
                "actual": actual,
                "passed": passed,
                "reason": reason,
            }
        )

        # Artificial delay to avoid hitting free-tier rate limits
        time.sleep(0.5)

    if len(TEST_CASES) % 4 != 0:
        console.print()
    console.print()
    return results


# ─── Reporting ────────────────────────────────────────────────────────────────


def show_prompt_diff() -> None:
    """Calculates and prints a rudimentary line-by-line diff between prompt versions.

    Highlights added rules to provide context for subsequent regressions.
    """
    v1_lines = set(PROMPT_V1.splitlines())
    added = [l for l in PROMPT_V2.splitlines() if l not in v1_lines and l.strip()]
    removed = [
        l
        for l in PROMPT_V1.splitlines()
        if l not in set(PROMPT_V2.splitlines()) and l.strip()
    ]

    console.print(Rule("[bold]Prompt Diff (V1 → V2)[/bold]", style="white"))

    for line in removed:
        console.print(f"  [red]- {line}[/red]")
    for line in added:
        console.print(f"  [green]+ {line}[/green]")
    console.print()


def render_table(v1_results: list[dict], v2_results: list[dict]) -> None:
    """Generates a summary table and detailed failure reports using Rich formatting.

    Identifies fixed tests and regressions, printing detailed LLM IO for regressions.
    """
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Regression Report", show_lines=True)
    table.add_column("#", style="bold")
    table.add_column("Customer Message", max_width=48)
    table.add_column("V1", justify="center")
    table.add_column("V2", justify="center")
    table.add_column("Delta", justify="center")

    v2_by_id = {r["id"]: r for r in v2_results}
    regressions, fixes = [], []

    for r1 in v1_results:
        r2 = v2_by_id[r1["id"]]
        snippet = (r1["input"][:45] + "...") if len(r1["input"]) > 48 else r1["input"]
        s1 = (
            "[bold green]PASS[/bold green]"
            if r1["passed"]
            else "[bold red]FAIL[/bold red]"
        )
        s2 = (
            "[bold green]PASS[/bold green]"
            if r2["passed"]
            else "[bold red]FAIL[/bold red]"
        )

        # Determine state transitions between prompt versions
        if r1["passed"] and not r2["passed"]:
            delta = "[bold red]REGRESSED ✗[/bold red]"
            regressions.append((r1, r2))
        elif not r1["passed"] and r2["passed"]:
            delta = "[bold green]FIXED ✓[/bold green]"
            fixes.append((r1, r2))
        else:
            delta = "[dim]same[/dim]"

        table.add_row(str(r1["id"]), snippet, s1, s2, delta)

    console.print(table)
    console.print()

    total = len(v1_results)
    v1_pass = sum(1 for r in v1_results if r["passed"])
    v2_pass = sum(1 for r in v2_results if r["passed"])

    console.print("[bold]Summary:[/bold]")
    console.print(f"  Prompt V1 : {v1_pass}/{total} passed")
    console.print(f"  Prompt V2 : {v2_pass}/{total} passed")
    console.print(f"  Regressions (V1 PASS → V2 FAIL) : {len(regressions)}")
    console.print(f"  Fixes       (V1 FAIL → V2 PASS) : {len(fixes)}")

    if regressions:
        console.print(Rule("[bold red]Regression Details[/bold red]", style="red"))
        for r1, r2 in regressions:
            console.print(f"\n[bold]Test Case #{r1['id']:02d}[/bold]")
            console.print(f"[dim]Expected:[/dim] {json.dumps(r1['expected'])}")

            # Print the detailed inputs and outputs to diagnose the failure
            display_model_input(PROMPT_V2, r1["input"])
            display_model_output(json.dumps(r2["actual"]))
            console.print(f"  [bold red]Failed Reason:[/bold red] {r2['reason']}\n")


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    """Initializes the client and orchestrates the regression harness."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        raise SystemExit(1)

    console.print(
        Panel.fit(
            "[bold yellow]Prompt Regression Harness[/bold yellow]\n"
            "[dim]Evaluates classification prompt iterations against test cases.[/dim]\n"
            "[dim]10 tests × 2 prompt versions[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    client = genai.Client(api_key=api_key)

    show_prompt_diff()

    v1_results = run_suite(client, PROMPT_V1, "Prompt V1 (baseline)", "cyan")
    v2_results = run_suite(client, PROMPT_V2, "Prompt V2 (+billing rule)", "magenta")

    render_table(v1_results, v2_results)


if __name__ == "__main__":
    main()
