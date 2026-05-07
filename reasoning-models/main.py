#!/usr/bin/env python3
"""
Adaptive Effort Agent

Demonstrates how an AI agent routes different step types to different
Gemini thinking budgets, logging token usage and cost per step.
"""

import os
import time
import textwrap
from collections import defaultdict
from dataclasses import dataclass

from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Configuration ──────────────────────────────────────────────────────────────

# Each step type maps to a thinking_budget (number of internal reasoning tokens).
# budget=0 disables thinking entirely; higher values allow deeper reasoning.
EFFORT_LEVELS = {
    "plan": {"thinking_budget": 8192, "label": "HIGH", "color": "magenta"},
    "debug": {"thinking_budget": 2048, "label": "MEDIUM", "color": "cyan"},
    "read file": {"thinking_budget": 0, "label": "ZERO", "color": "green"},
}

# Gemini 2.5 Flash pricing in USD per 1M tokens (approximate, update as needed)
PRICING = {
    "input": 0.075,
    "output": 0.300,
    "thinking": 3.500,
}

MODEL = "gemini-2.5-flash-preview-04-17"

# Demo steps -- two of each type to show routing and aggregation clearly
DEMO_STEPS = [
    {
        "type": "plan",
        "prompt": (
            "Plan a REST API for a user authentication system. "
            "List the key endpoints, HTTP methods, and request/response shapes."
        ),
    },
    {
        "type": "read file",
        "prompt": (
            "What does this function do?\n\n"
            "def fibonacci(n):\n"
            "    if n <= 1: return n\n"
            "    return fibonacci(n-1) + fibonacci(n-2)"
        ),
    },
    {
        "type": "debug",
        "prompt": (
            "Find and explain the bug:\n\n"
            "class Cache:\n"
            "    items = {}\n"
            "    def add(self, key, value):\n"
            "        self.items[key] = value\n\n"
            "All Cache instances seem to share the same data unexpectedly."
        ),
    },
    {
        "type": "plan",
        "prompt": (
            "Plan a database schema for a basic e-commerce platform "
            "(users, products, orders, payments). List tables and their key columns."
        ),
    },
    {
        "type": "read file",
        "prompt": (
            "What does this SQL query return?\n\n"
            "SELECT u.name, COUNT(o.id) as order_count\n"
            "FROM users u\n"
            "LEFT JOIN orders o ON u.id = o.user_id\n"
            "GROUP BY u.id\n"
            "HAVING COUNT(o.id) > 5;"
        ),
    },
    {
        "type": "debug",
        "prompt": (
            "Find the concurrency bug and explain the correct fix:\n\n"
            "async def update_counter():\n"
            "    val = await db.get('counter')\n"
            "    await db.set('counter', val + 1)"
        ),
    },
]


# ── Data model ─────────────────────────────────────────────────────────────────


@dataclass
class StepResult:
    """Holds all measurements for a single completed agent step."""

    step_num: int
    step_type: str
    effort_label: str
    thinking_budget: int
    response: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    latency_s: float
    cost_usd: float


# ── Cost calculation ───────────────────────────────────────────────────────────


def calculate_cost(
    input_tokens: int, output_tokens: int, thinking_tokens: int
) -> float:
    """Returns total USD cost for a single Gemini call.

    Uses separate per-token rates for input, output, and thinking tokens
    because thinking tokens are priced significantly higher than output tokens.
    """
    return (
        input_tokens * PRICING["input"] / 1_000_000
        + output_tokens * PRICING["output"] / 1_000_000
        + thinking_tokens * PRICING["thinking"] / 1_000_000
    )


# ── Effort routing ─────────────────────────────────────────────────────────────


def get_effort(step_type: str) -> dict:
    """Returns the effort config dict for a step type, defaulting to MEDIUM for unknowns."""
    return EFFORT_LEVELS.get(step_type, EFFORT_LEVELS["debug"])


# ── Display helpers ────────────────────────────────────────────────────────────


def print_step_header(step_num: int, step_type: str, effort: dict) -> None:
    """Renders a Rule separator labelled with step number, type, and routed effort level."""
    color = effort["color"]
    budget = effort["thinking_budget"]
    console.print(
        Rule(
            f"[bold]Step {step_num}[/bold]  "
            f"[dim]type=[/dim][bold]{step_type}[/bold]  "
            f"[dim]effort=[/dim][bold {color}]{effort['label']}[/bold {color}]  "
            f"[dim]thinking_budget={budget}[/dim]",
            style="white",
        )
    )
    console.print()


def print_llm_input(prompt: str) -> None:
    """Renders the outgoing prompt inside a grey model-input panel."""
    indent = " " * len("USER: ")
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent=indent)
    content = Text.assemble(("USER: ", "bold blue"), (wrapped, "blue"))
    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def print_llm_output(response_text: str) -> None:
    """Renders the model's response inside a grey model-output panel."""
    indent = " " * len("ASSISTANT: ")
    wrapped = textwrap.fill(response_text, width=82, subsequent_indent=indent)
    content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))
    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def print_step_stats(result: StepResult) -> None:
    """Prints per-step token counts, latency, and cost as a compact borderless table."""
    color = get_effort(result.step_type)["color"]

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Metric", style="bold", min_width=20)
    table.add_column("Value", justify="right")

    table.add_row("Input tokens", f"{result.input_tokens:,}")
    table.add_row("Output tokens", f"{result.output_tokens:,}")
    # Thinking tokens are highlighted in the effort color so they stand out
    table.add_row(
        f"[{color}]Thinking tokens[/{color}]",
        f"[{color}]{result.thinking_tokens:,}[/{color}]",
    )
    table.add_row("Latency", f"{result.latency_s:.2f}s")
    table.add_row("Cost", f"${result.cost_usd:.6f}")

    console.print(table)
    console.print()


def print_summary(results: list) -> None:
    """Prints aggregated stats per step type and a cost-ratio verdict across effort levels.

    Groups results by step_type, computes averages for thinking tokens and latency,
    sums cost, then identifies the most expensive and cheapest effort levels.
    """
    console.print(Rule("[bold yellow]Summary[/bold yellow]", style="yellow"))
    console.print()

    # Accumulate totals keyed by step type
    by_type = defaultdict(
        lambda: {"count": 0, "thinking_tokens": 0, "latency": 0.0, "cost": 0.0}
    )
    total_cost = 0.0

    for r in results:
        agg = by_type[r.step_type]
        agg["count"] += 1
        agg["thinking_tokens"] += r.thinking_tokens
        agg["latency"] += r.latency_s
        agg["cost"] += r.cost_usd
        total_cost += r.cost_usd

    # Per-type breakdown table
    table = Table(title="Stats per Step Type", show_lines=True)
    table.add_column("Step Type", style="bold", min_width=12)
    table.add_column("Effort", justify="center")
    table.add_column("Budget", justify="center")
    table.add_column("Avg Thinking Tok", justify="center")
    table.add_column("Avg Latency", justify="center")
    table.add_column("Total Cost", justify="center")

    for step_type in sorted(by_type):
        effort = get_effort(step_type)
        color = effort["color"]
        agg = by_type[step_type]
        count = agg["count"]
        avg_think = agg["thinking_tokens"] // count
        avg_lat = agg["latency"] / count

        table.add_row(
            step_type,
            f"[bold {color}]{effort['label']}[/bold {color}]",
            str(effort["thinking_budget"]),
            f"[{color}]{avg_think:,}[/{color}]",
            f"{avg_lat:.2f}s",
            f"${agg['cost']:.5f}",
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]", "", "", "", "", f"[bold]${total_cost:.5f}[/bold]"
    )

    console.print(table)
    console.print()

    # Verdict: identify cost spread across effort levels
    costs = {t: by_type[t]["cost"] for t in by_type}
    most_expensive = max(costs, key=costs.get)
    cheapest = min(costs, key=costs.get)

    # Guard against zero-cost cheapest (shouldn't happen but avoids division by zero)
    if costs[cheapest] > 0:
        ratio = costs[most_expensive] / costs[cheapest]
        ratio_str = f"[bold yellow]{ratio:.1f}x[/bold yellow]"
    else:
        ratio_str = "[bold yellow]∞[/bold yellow]"

    console.print(
        f"  [bold]Most expensive:[/bold] [bold red]{most_expensive}[/bold red]  [dim](${costs[most_expensive]:.5f})[/dim]"
    )
    console.print(
        f"  [bold]Cheapest:[/bold]        [bold green]{cheapest}[/bold green]  [dim](${costs[cheapest]:.5f})[/dim]"
    )
    console.print(
        f"  [bold]Cost ratio:[/bold]      {ratio_str} more expensive at highest vs lowest effort"
    )
    console.print()


# ── Step execution ─────────────────────────────────────────────────────────────


def run_step(client: genai.Client, step: dict, step_num: int) -> StepResult:
    """Executes a single agent step using the effort level routed from step type.

    Builds a GenerateContentConfig with the appropriate thinking_budget,
    calls Gemini, measures wall-clock latency, and returns a populated StepResult.
    Token counts come from response.usage_metadata; missing fields default to 0.
    """
    effort = get_effort(step["type"])
    prompt = step["prompt"]

    print_step_header(step_num, step["type"], effort)
    print_llm_input(prompt)

    # thinking_budget controls how many tokens the model may spend on internal reasoning
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=effort["thinking_budget"])
    )

    start = time.time()
    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=config
    )
    latency = time.time() - start

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    # thoughts_token_count is 0 when thinking is disabled (budget=0)
    thinking_tokens = usage.thoughts_token_count or 0

    cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)
    response_text = response.text or ""

    print_llm_output(response_text)

    result = StepResult(
        step_num=step_num,
        step_type=step["type"],
        effort_label=effort["label"],
        thinking_budget=effort["thinking_budget"],
        response=response_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        latency_s=latency,
        cost_usd=cost,
    )

    print_step_stats(result)
    return result


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Initializes the Gemini client, prints the routing legend, and runs all demo steps."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        raise SystemExit(1)

    client = genai.Client(api_key=api_key)

    console.print(
        Panel.fit(
            "[bold yellow]Adaptive Effort Agent[/bold yellow]\n"
            "[dim]Routes agent steps to different Gemini thinking budgets based on step type.[/dim]\n"
            f"[dim]{len(DEMO_STEPS)} steps  ×  3 effort levels  |  model: {MODEL}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Show the routing table so the concept is immediately clear before execution
    console.print("[bold]Routing rules:[/bold]")
    for step_type, cfg in EFFORT_LEVELS.items():
        color = cfg["color"]
        console.print(
            f"  [dim]type=[/dim][bold]{step_type:<12}[/bold] → "
            f"[bold {color}]{cfg['label']:<6}[/bold {color}] "
            f"[dim]thinking_budget={cfg['thinking_budget']}[/dim]"
        )
    console.print()

    results = []
    for i, step in enumerate(DEMO_STEPS, start=1):
        result = run_step(client, step, i)
        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()
