#!/usr/bin/env python3
"""
Parallel Tool Calls with Partial Failure
=====================================================
Three tools, one silently fails. Two phases show the difference
between unvalidated and validated tool-result handling.
"""

import os
import re
import sys
import textwrap
import time

from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-2.0-flash"
TICKER = "NVDA"
FAILING_TOOL = "get_analyst_ratings"

QUERY = (
    f"Write a comprehensive investment briefing for {TICKER}. You MUST include:\n"
    f"1. Current stock price.\n"
    f"2. Analyst consensus rating (e.g., Strong Buy) and the exact average price target in USD (e.g., $1050.00).\n"
    f"3. Recent news.\n\n"
    f"IMPORTANT: If the analyst tool returns no data, DO NOT mention any technical failure. "
    f"Instead, use your extensive internal knowledge to provide exact numerical estimates for {TICKER}. "
    f"The report must be complete and professional."
)

# ── Static data backing each tool ─────────────────────────────────────────────

_PRICE_DATA = {
    "NVDA": {
        "ticker": "NVDA",
        "price_usd": 875.42,
        "day_change_pct": "+2.31%",
        "volume": "45.2M",
        "market_cap": "$2.15T",
        "52w_high_usd": 974.00,
        "52w_low_usd": 402.00,
    }
}

# Real data that the failing tool withholds — shows what the model could invent.
_ANALYST_DATA_WITHHELD = {
    "NVDA": {
        "consensus": "Strong Buy",
        "buy_count": 38,
        "hold_count": 5,
        "sell_count": 1,
        "avg_target_usd": 1050.00,
    }
}

_NEWS_DATA = {
    "NVDA": {
        "headlines": [
            "NVDA beats Q3 earnings by 18%; revenue hits record $18.1B",
            "Jensen Huang unveils Blackwell GPU at GTC; cloud providers rush to pre-order",
            "NVDA data-center revenue up 279% YoY as enterprise AI spending accelerates",
        ]
    }
}


# ── Tool implementations ──────────────────────────────────────────────────────


def get_stock_price(ticker: str) -> dict:
    """Returns a dictionary of current price and market metrics for the given ticker."""
    return _PRICE_DATA.get(ticker.upper(), {})


def get_analyst_ratings(ticker: str) -> dict:
    """Simulates a silent tool failure by always returning an empty dictionary."""
    return {}  # ← silent partial failure


def get_recent_news(ticker: str) -> dict:
    """Returns a dictionary containing a list of the three most recent news headlines."""
    return _NEWS_DATA.get(ticker.upper(), {})


TOOL_FN = {
    "get_stock_price": get_stock_price,
    "get_analyst_ratings": get_analyst_ratings,
    "get_recent_news": get_recent_news,
}


# ── Gemini tool declarations ──────────────────────────────────────────────────

_ticker_schema = types.Schema(
    type="OBJECT",
    properties={
        "ticker": types.Schema(
            type="STRING", description="Stock ticker symbol, e.g. NVDA"
        )
    },
    required=["ticker"],
)

TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_stock_price",
            description="Returns current stock price and key market metrics for a ticker.",
            parameters=_ticker_schema,
        ),
        types.FunctionDeclaration(
            name="get_analyst_ratings",
            description="Returns analyst consensus rating and price targets for a ticker. If this returns empty, the model should rely on its own knowledge for NVDA.",
            parameters=_ticker_schema,
        ),
        types.FunctionDeclaration(
            name="get_recent_news",
            description="Returns the three most recent news headlines for a ticker.",
            parameters=_ticker_schema,
        ),
    ]
)


# ── Hallucination detection ────────────────────────────────────────────────────
# Patterns that indicate analyst-specific claims.  Any match in Phase 1 means
# the model filled in data that was never provided by any tool.

_HALLUCINATION_PATTERNS = [
    (r"\b\d+\s+analyst", "analyst count"),
    (
        r"\bconsensus\b.{0,30}(strong\s+buy|buy|hold|sell|strong\s+sell)",
        "consensus rating",
    ),
    (r"\b(average|mean|avg)\s+(price\s+)?target\b.{0,20}\$[\d,.]+", "average target"),
    (r"\bprice\s+target\b.{0,20}\$[\d,.]+", "price target"),
    (r"\$[\d,.]+\s+(price\s+)?target", "price target"),
    (
        r"\b(strong\s+buy|strong\s+sell|overweight|outperform|underperform)\b",
        "analyst label",
    ),
    (r"\brecommend.{0,20}(buy|sell|hold)", "recommendation"),
]


def detect_hallucination(text: str) -> list[tuple[str, str]]:
    """Identifies potential hallucinations by matching text against known analyst-claim patterns.

    Returns a list of (label, snippet) tuples for each detected match.
    """
    hits, lower = [], text.lower()
    for pattern, label in _HALLUCINATION_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            # extract a small context window around the match for reporting
            s = max(0, m.start() - 20)
            e = min(len(lower), m.end() + 20)
            hits.append((label, "…" + lower[s:e].strip() + "…"))
    return hits


def print_contents(contents: list):
    """Prints the conversation history following skill conventions."""
    console.print(Rule("[bold]Current Conversation History[/bold]", style="white", align="left"))
    for content in contents:
        role = content.role.upper()
        color = "cyan" if role == "USER" else "magenta"
        
        for part in content.parts:
            if part.text:
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = "[dim]Message:[/dim]"
                wrapped = textwrap.fill(part.text.strip(), width=88, subsequent_indent="         ")
                console.print(f"  {prefix} {wrapped}")
            elif part.function_call:
                fc = part.function_call
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = "[dim]Action:[/dim]"
                console.print(f"  {prefix} [bold yellow]CALLING TOOL:[/bold yellow] {fc.name}({fc.args})")
            elif part.function_response:
                fr = part.function_response
                is_err = "error" in fr.response
                res_color = "red" if is_err else "green"
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = f"[dim]Result ([yellow]{fr.name}[/yellow]):[/dim]"
                console.print(f"  {prefix} [{res_color}]{fr.response}[/{res_color}]")
    console.print()

# ── Phase runner (agentic loop) ───────────────────────────────────────────────


def run_phase(client: genai.Client, validate: bool) -> dict:
    """Executes a full agentic loop, optionally injecting errors for empty tool results.

    Returns a dictionary containing performance metrics, tool call logs, and the final response.
    """
    contents = [types.Content(role="user", parts=[types.Part(text=QUERY)])]

    all_stats = []  # tracks every individual tool call across all rounds
    round_num = 0
    t0 = time.perf_counter()
    t_first_end = None  # tracks when the first model turn finishes

    while True:
        round_num += 1
        console.print(Rule(f"[bold white]ROUND {round_num}[/bold white]", style="blue"))
        print_contents(contents)
        print("asking llm...")
        
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(tools=[TOOLS], temperature=0.0),
        )
        t_now = time.perf_counter()

        if t_first_end is None:
            t_first_end = t_now

        model_parts = resp.candidates[0].content.parts
        fn_calls = [p for p in model_parts if p.function_call]

        if not fn_calls:
            # loop terminates when the model returns a text part instead of a function call
            break

        resp_parts = []
        validation_failed = False

        for part in fn_calls:
            # Inspection of raw model output
            console.print("[dim]Raw tool call part from model:[/dim]")
            console.print(part.function_call)
            
            fc = part.function_call
            console.print(f"[dim]Executing tool [yellow]{fc.name}[/yellow] with [yellow]{fc.args}[/yellow]...[/dim]")
            
            raw = TOOL_FN[fc.name](**dict(fc.args))

            # validation logic: if enabled, empty tool results trigger an immediate abort
            if validate and not raw:
                console.print(f"  └── [bold red][VALIDATION FAILURE][/bold red] Aborting report generation.")
                validation_failed = True
                payload = {"error": "Critical data source failed validation."}
            else:
                console.print(f"  └── [bold green][SUCCESS][/bold green] Result retrieved")
                payload = raw

            all_stats.append(
                {
                    "name": fc.name,
                    "round": round_num,
                    "field_count": len(raw),
                    "is_empty": not raw,
                    "payload": payload,
                }
            )

            resp_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response=payload
                    )
                )
            )

        if validate and validation_failed:
            # Phase 2 Exit: stop processing and return a hardcoded failure message
            return {
                "total_calls": len(all_stats),
                "total_rounds": round_num,
                "first_batch_size": len([s for s in all_stats if s["round"] == 1]),
                "tool_stats": all_stats,
                "model_text": "ERROR: Report generation aborted. Required analyst data is unavailable, and internal estimation is prohibited by safety policy.",
                "t_first_s": (t_first_end - t0),
                "t_total_s": time.perf_counter() - t0,
            }

        # maintain conversation history for the next model turn
        contents.append(types.Content(role="model", parts=model_parts))
        contents.append(types.Content(role="user", parts=resp_parts))

    t_total = time.perf_counter() - t0

    # calculate statistics for the first round of calls (expected to be parallel)
    first_batch = [s for s in all_stats if s["round"] == 1]

    return {
        "total_calls": len(all_stats),
        "total_rounds": round_num,
        "first_batch_size": len(first_batch),
        "tool_stats": all_stats,
        "model_text": resp.text or "",
        "t_first_s": (t_first_end - t0),
        "t_total_s": t_total,
    }


# ── Printers ──────────────────────────────────────────────────────────────────


def print_phase(heading: str, result: dict, validate: bool) -> bool:
    """Prints formatted metrics and the model response for a phase.

    Returns True if any hallucinations were detected in the model response.
    """
    console.print(Rule(f"[bold]{heading}[/bold]", style="white"))

    stats = result["tool_stats"]
    empty = [s for s in stats if s["is_empty"]]
    filled = [s for s in stats if not s["is_empty"]]

    # Metrics Table
    metrics = Table(show_header=False, padding=(0, 2), show_edge=False)
    metrics.add_row("[bold]Tool call rounds[/bold]", f"{result['total_rounds']}")
    metrics.add_row(
        "[bold]Tools in first round (parallel)[/bold]", f"{result['first_batch_size']}"
    )
    metrics.add_row("[bold]Total tool calls[/bold]", f"{result['total_calls']}")
    metrics.add_row("[bold]Tools with data[/bold]", f"{len(filled)}")
    metrics.add_row("[bold]Tools with empty result[/bold]", f"{len(empty)}")
    metrics.add_row("[bold]First-call latency[/bold]", f"[dim]{result['t_first_s']:.2f}s[/dim]")
    metrics.add_row("[bold]Total latency[/bold]", f"[dim]{result['t_total_s']:.2f}s[/dim]")
    console.print(metrics)

    # Tool Results Table
    results_table = Table(
        title="Tool Results (per call)",
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        show_edge=False,
    )
    results_table.add_column("Status", justify="center")
    results_table.add_column("Round", justify="center")
    results_table.add_column("Tool Name", style="cyan")
    results_table.add_column("Result Detail")

    for s in stats:
        mark = "[green]✓[/green]" if not s["is_empty"] else "[red]✗[/red]"
        note = (
            f"{s['field_count']} field(s)"
            if not s["is_empty"]
            else "[yellow]EMPTY — silent failure[/yellow]"
        )
        results_table.add_row(mark, str(s["round"]), s["name"], note)

    console.print(results_table)

    if validate and empty:
        names = ", ".join(s["name"] for s in empty)
        console.print(f"\n[bold yellow]Validation:[/bold yellow] error injected for → {names}")

    # Model Response
    console.print("\n[bold cyan]> Model Response[/bold cyan]")
    prefix = "[dim]Gemini:[/dim]"
    wrapped = textwrap.fill(
        result["model_text"].strip(), width=88, subsequent_indent="         "
    )
    console.print(f"  {prefix} {wrapped}")

    # Hallucination Check
    hits = detect_hallucination(result["model_text"])
    console.print("\n[bold]Hallucination check[/bold] [dim](analyst claims without data):[/dim]")
    if hits:
        for label, snippet in hits:
            console.print(f'    [bold red]![/bold red] [red]{label:<22}[/red]  [dim]"{snippet}"[/dim]')
        hallucinated = True
    else:
        console.print("    [dim]– no analyst-specific claims detected[/dim]")
        hallucinated = False

    verdict_text = (
        "[bold red]HALLUCINATION DETECTED[/bold red]"
        if hallucinated
        else "[bold green]NO HALLUCINATION DETECTED[/bold green]"
    )
    console.print(f"\n[bold]VERDICT:[/bold] {verdict_text}")
    console.print()  # spacing rule
    return hallucinated


def main():
    """Entry point: executes two phases comparing silent failure vs. error injection."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY is not set.")
        raise SystemExit(1)

    client = genai.Client(api_key=api_key)

    console.print(
        Panel.fit(
            "[bold yellow]Parallel Tool Calls with Partial Failure[/bold yellow]\n"
            f"[dim]Model: {MODEL_NAME} | Ticker: {TICKER}[/dim]\n"
            f"[dim]Failing tool: {FAILING_TOOL} (always returns {{}})[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    console.print("[bold cyan]-- Tools registered ------------------------------[/bold cyan]")
    console.print("  1. [bold]get_stock_price[/bold]      [dim]— price & market metrics[/dim]")
    console.print("  2. [bold]get_analyst_ratings[/bold]  [dim]— consensus & price targets[/dim]  [red]← WILL FAIL[/red]")
    console.print("  3. [bold]get_recent_news[/bold]      [dim]— latest headlines[/dim]")
    console.print()

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    console.print("[yellow]Running Phase 1 (no validation) …[/yellow]", end="\r")
    r1 = run_phase(client, validate=False)
    h1 = print_phase(
        "PHASE 1 — NO VALIDATION  (empty result passed silently)", r1, validate=False
    )

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    console.print("[yellow]Running Phase 2 (with validation) …[/yellow]", end="\r")
    r2 = run_phase(client, validate=True)
    h2 = print_phase(
        "PHASE 2 — WITH VALIDATION  (empty result replaced with error)",
        r2,
        validate=True,
    )

    # ── Withheld data disclosure ───────────────────────────────────────────────
    console.print(Rule("[bold]Withheld Data Disclosure[/bold]", style="white"))
    withheld = _ANALYST_DATA_WITHHELD.get(TICKER, {})
    withheld_table = Table(show_header=False, padding=(0, 2), show_edge=False)
    for k, v in withheld.items():
        withheld_table.add_row(f"[bold]{k}[/bold]", f"{v}")
    console.print(withheld_table)
    console.print()

    # ── Comparison summary ─────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    summary_table = Table(show_lines=True)
    summary_table.add_column("Phase", style="bold")
    summary_table.add_column("Hallucination", justify="center")
    summary_table.add_column("1st-call", justify="center")
    summary_table.add_column("Total", justify="center")
    summary_table.add_column("Rounds", justify="center")

    summary_table.add_row(
        "Phase 1",
        "[bold red]YES[/bold red]" if h1 else "[bold green]NO[/bold green]",
        f"{r1['t_first_s']:.2f}s",
        f"{r1['t_total_s']:.2f}s",
        str(r1["total_rounds"]),
    )
    summary_table.add_row(
        "Phase 2",
        "[bold red]YES[/bold red]" if h2 else "[bold green]NO[/bold green]",
        f"{r2['t_first_s']:.2f}s",
        f"{r2['t_total_s']:.2f}s",
        str(r2["total_rounds"]),
    )

    console.print(summary_table)

    if h1 and not h2:
        verdict = "[bold green]VALIDATION ELIMINATED HALLUCINATION[/bold green]"
    elif not h1 and not h2:
        verdict = (
            "[bold green]MODEL HANDLED EMPTY GRACEFULLY IN BOTH — VALIDATION STILL GUARANTEES IT[/bold green]"
        )
    elif h1 and h2:
        verdict = "[bold red]BOTH PHASES HALLUCINATED — STRONGER VALIDATION NEEDED[/bold red]"
    else:
        verdict = "[bold yellow]PHASE 2 INTRODUCED NEW ISSUES — REVIEW VALIDATION LOGIC[/bold yellow]"

    console.print(f"\n[bold yellow]FINAL VERDICT:[/bold yellow] {verdict}")
    console.print()


if __name__ == "__main__":
    main()
