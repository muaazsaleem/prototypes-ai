import textwrap
from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from models import Evidence, FactCheckReport, VoteResult

console = Console()

VERDICT_STYLE = {
    "TRUE": ("green", "✓ TRUE"),
    "FALSE": ("red", "✗ FALSE"),
    "UNVERIFIABLE": ("yellow", "? UNVERIFIABLE"),
}


def build_report(
    passage: str,
    evidences: list[Evidence],
    results: list[VoteResult],
) -> FactCheckReport:
    """Assembles a FactCheckReport from raw voting results.

    overall_credibility_score is the fraction of claims that received a TRUE verdict.
    Guards against division by zero when the passage yielded no claims.
    """
    true_count = sum(1 for r in results if r.final_verdict == "TRUE")
    total = len(results)
    overall_score = (true_count / total) if total > 0 else 0.0

    return FactCheckReport(
        passage=passage,
        total_claims=total,
        results=results,
        overall_credibility_score=overall_score,
    )


def _render_vote_distribution(votes: list[str]) -> str:
    """Returns a compact vote-tally string like 'TRUE×4  FALSE×1' for display in panel titles.

    Only includes verdict labels that actually appear in votes; skips zero-count labels.
    Order is fixed (TRUE → FALSE → UNVERIFIABLE) for consistent left-to-right reading.
    """
    counts = Counter(votes)
    parts = [
        f"{v}×{counts[v]}" for v in ["TRUE", "FALSE", "UNVERIFIABLE"] if v in counts
    ]
    return "  ".join(parts)


def _credibility_bar(score: float, width: int = 20) -> Text:
    """Returns a visual X/. progress bar for the overall credibility score.

    Color follows the standard threshold: green ≥ 80%, yellow ≥ 50%, red below 50%.
    """
    filled = round(score * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
    return Text(bar, style=color)


def display_report(report: FactCheckReport, evidences: list[Evidence]) -> None:
    """Prints the full fact-check report to the terminal using rich panels.

    Renders one panel per claim showing evidence, verdict, confidence, and vote distribution,
    followed by a summary table and an overall credibility score.
    evidences must be in the same order as report.results.
    """
    console.print(
        Panel(
            report.passage,
            title="[bold]Passage Under Review[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print()

    console.print(Rule("[bold]Claims[/bold]", style="white"))
    console.print()

    for result, evidence in zip(report.results, evidences):
        color, label = VERDICT_STYLE.get(
            result.final_verdict, ("white", result.final_verdict)
        )

        # Build a rich Text object so each section can have its own color style
        content = Text()
        content.append(f"{result.claim}\n\n", style="bold")

        if evidence.supporting:
            content.append("Supporting:\n", style="bold green")
            for item in evidence.supporting:
                wrapped = textwrap.fill(item, width=76, subsequent_indent="    ")
                content.append(f"  + {wrapped}\n", style="green")

        if evidence.contradicting:
            content.append("\nContradicting:\n", style="bold red")
            for item in evidence.contradicting:
                wrapped = textwrap.fill(item, width=76, subsequent_indent="    ")
                content.append(f"  - {wrapped}\n", style="red")

        # Reasoning is secondary metadata — dim + italic
        content.append("\nReasoning: ", style="bold dim")
        content.append(result.reasoning, style="italic dim")

        vote_dist = _render_vote_distribution(result.individual_votes)
        confidence_pct = int(result.confidence * 100)

        console.print(
            Panel(
                content,
                title=(
                    f"[bold {color}]{label}[/bold {color}]"
                    f"  [dim]|  confidence: {confidence_pct}%  |  votes: {vote_dist}[/dim]"
                ),
                border_style=color,
                padding=(1, 2),
            )
        )

    console.print()
    _display_summary_table(report)
    console.print()


def _display_summary_table(report: FactCheckReport) -> None:
    """Prints a summary table and a credibility bar under a yellow Rule.

    Table uses show_lines=True (final summary style). Color-codes the credibility bar:
    green ≥ 80%, yellow ≥ 50%, red below 50%.
    """
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_lines=True
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Claim", min_width=40)
    table.add_column("Verdict", justify="center", width=18)
    table.add_column("Confidence", justify="center", width=12)
    table.add_column("Votes", justify="center", width=22, style="dim")

    for result in report.results:
        color, label = VERDICT_STYLE.get(
            result.final_verdict, ("white", result.final_verdict)
        )
        claim_short = (
            (result.claim[:57] + "...") if len(result.claim) > 60 else result.claim
        )
        vote_dist = _render_vote_distribution(result.individual_votes)
        table.add_row(
            str(report.results.index(result) + 1),
            claim_short,
            f"[bold {color}]{label}[/bold {color}]",
            f"{int(result.confidence * 100)}%",
            vote_dist,
        )

    # Totals row
    true_count = sum(1 for r in report.results if r.final_verdict == "TRUE")
    false_count = sum(1 for r in report.results if r.final_verdict == "FALSE")
    unverifiable_count = sum(
        1 for r in report.results if r.final_verdict == "UNVERIFIABLE"
    )
    table.add_section()
    table.add_row(
        "",
        "[bold]Total[/bold]",
        (
            f"[bold][green]{true_count} true[/green]"
            f"  [red]{false_count} false[/red]"
            f"  [yellow]{unverifiable_count} ?[/yellow][/bold]"
        ),
        "",
        "",
    )

    console.print(table)
    console.print()

    # Credibility bar
    bar = _credibility_bar(report.overall_credibility_score)
    score_pct = int(report.overall_credibility_score * 100)
    color = "green" if score_pct >= 80 else "yellow" if score_pct >= 50 else "red"
    console.print(
        f"  [bold]Credibility[/bold]  ",
        end="",
        highlight=False,
    )
    console.print(bar, end="")
    console.print(
        f"  [{color}]{true_count}/{report.total_claims}  ({score_pct}%)[/{color}]"
    )
