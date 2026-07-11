#!/usr/bin/env python3
"""
paper2code -- Paper-to-Code Agent

Usage:
    python main.py <paper.pdf> <output.py>

Reads the paper at <paper.pdf>, runs a ReAct loop powered by Claude,
and writes the final implementation to <output.py>.

All processing is local -- only the Anthropic API call leaves the machine.
Set ANTHROPIC_API_KEY in your environment before running.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from rich.console import Console
from rich.panel import Panel

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Implement a research paper as working Python code."
    )
    parser.add_argument(
        "paper",
        help="Path to the input paper (PDF or .txt).",
    )
    parser.add_argument(
        "output",
        help="Path where the generated Python file will be written.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Maximum ReAct iterations (default: 12).",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold yellow]paper2code[/bold yellow]\n"
            "[dim]Paper-to-Code Agent[/dim]\n"
            f"[dim]Input: {args.paper} | Max Steps: {args.max_steps}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Validate API key early so the error is clear
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]ERROR:[/bold red] GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    # Lazy imports so --help is always fast
    from ingest import load_paper
    from react_loop import AgentState, run, MAX_STEPS
    import react_loop as rl

    if args.max_steps != 12:
        rl.MAX_STEPS = args.max_steps

    console.print(f"[bold cyan]-- Loading Paper --------------------------------------[/bold cyan]")
    t0 = time.monotonic()

    try:
        paper_text = load_paper(args.paper)
    except FileNotFoundError:
        console.print(f"[bold red]ERROR:[/bold red] Paper not found: {args.paper}")
        sys.exit(1)
        
    char_count = len(paper_text)
    console.print(f"  [dim]Loaded {char_count:,} characters from paper.[/dim]\n")

    state = AgentState(
        paper_text=paper_text,
        output_path=os.path.abspath(args.output),
    )

    try:
        final_code = run(state)
    except RuntimeError as e:
        console.print(f"\n[bold red]ERROR:[/bold red] {e}")
        sys.exit(1)

    # Write final code to disk
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_code)

    elapsed = time.monotonic() - t0
    lines = final_code.count("\n") + 1
    
    from rich.rule import Rule
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print(f"  [green]Done in {elapsed:.1f}s[/green]")
    console.print(f"  [green]{lines} lines written to {out_path}[/green]\n")


if __name__ == "__main__":
    main()
