import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from orchestrator import review_pr
from sample_diff import SAMPLE_DIFF

console = Console()

SEVERITY_COLORS = {
    "critical": "bold red",
    "high": "orange3",
    "medium": "yellow",
    "low": "dim",
}

VERDICT_COLORS = {
    "approve": "green",
    "request_changes": "red",
    "comment": "yellow",
}


def display_review(decision) -> None:
    """Renders a ReviewDecision to the terminal using rich formatting.

    Displays the final verdict, a summary panel, a findings table with
    severity-based color coding, and a list of key decisions.
    """
    # Map the verdict to its corresponding color for emphasized output
    verdict_color = VERDICT_COLORS.get(decision.verdict, "white")
    console.print(
        f"\n[bold]Verdict:[/bold] [{verdict_color}]{decision.verdict.upper()}[/{verdict_color}]\n"
    )

    # Use a Panel to encapsulate the summary text for better visual hierarchy
    console.print(
        Panel(decision.summary, title="[bold]Summary[/bold]", border_style="blue")
    )

    if decision.findings:
        # Create a table to display findings if any are present
        table = Table(title="Consolidated Findings", show_lines=True, expand=True)
        table.add_column("Severity", width=10)
        table.add_column("Description", ratio=2)
        table.add_column("Suggestion", ratio=2)

        for f in decision.findings:
            # Color each row based on the severity of the finding
            color = SEVERITY_COLORS.get(f.severity, "white")
            table.add_row(
                f"[{color}]{f.severity}[/{color}]",
                f.description,
                f.suggestion,
            )

        console.print(table)

    if decision.key_decisions:
        # List key decisions that were extracted and stored in repository memory
        console.print("\n[bold]Key Decisions stored in memory:[/bold]")
        for kd in decision.key_decisions:
            console.print(f"  • {kd}")

    console.print()
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()


def main() -> None:
    """Entry point for the multi-agent code review CLI.

    Parses command-line arguments, determines the source of the diff
    (file or sample), and orchestrates the review process.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Multi-Agent Code Reviewer[/bold yellow]\n"
            "[dim]Fans out a PR diff to specialist agents, then consolidates with a critic.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    parser = argparse.ArgumentParser(
        description="Multi-Agent Code Reviewer — fans out a PR diff to specialist agents, then consolidates with a critic."
    )

    parser.add_argument(
        "--repo", default="demo-repo", help="Repository name (used for memory scoping)"
    )
    parser.add_argument(
        "--diff", help="Path to a unified diff file (omit to use built-in sample diff)"
    )
    args = parser.parse_args()

    if args.diff:
        # Load the diff content from the specified file path
        diff = Path(args.diff).read_text()
    else:
        # Default to a built-in sample diff if none is provided via CLI
        diff = SAMPLE_DIFF
        console.print("[dim]No --diff provided, using the built-in sample diff.[/dim]")

    # Run the full review pipeline through the orchestrator
    decision = review_pr(args.repo, diff)
    display_review(decision)


if __name__ == "__main__":
    main()
