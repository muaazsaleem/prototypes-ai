from rich.console import Console

from agents import (
    run_critic_agent,
    run_logic_agent,
    run_security_agent,
    run_style_agent,
)
from checkpoint import get_review_id, load_checkpoint, save_checkpoint
from memory import format_memory_context, load_repo_memory, save_review_decision
from models import ReviewDecision, SpecialistReport

console = Console()


def _run_specialist(
    review_id: str, agent_name: str, run_fn, diff: str
) -> SpecialistReport:
    """Runs a single specialist agent, returning a cached result if one exists.

    Checks the checkpoint store to see if this agent has already completed
    its task for the given review ID. If not, it executes the agent function
    and saves the resulting report as a checkpoint.
    """
    cached = load_checkpoint(review_id, agent_name)
    if cached:
        # Load the specialist's report from the filesystem to save time and tokens
        console.print(f"  [dim]✓ {agent_name} agent — loaded from checkpoint[/dim]")
        return SpecialistReport.from_dict(agent_name, cached)

    console.print(f"  [yellow]→ {agent_name} agent running...[/yellow]")
    report = run_fn(diff)

    # Persist the report so subsequent runs can resume from this point
    save_checkpoint(review_id, agent_name, report.to_dict())
    console.print(f"  [green]✓ {agent_name} agent done — checkpoint saved[/green]")
    return report


def review_pr(repo: str, diff: str) -> ReviewDecision:
    """Runs the full multi-agent review pipeline for a PR diff.

    Orchestrates the three-phase process: specialist analysis, memory
    retrieval, and final consolidation by the critic agent. Returns the
    consolidated ReviewDecision.
    """
    review_id = get_review_id(repo, diff)

    console.print(
        f"\n[bold]Repo:[/bold] {repo}  [bold]Review ID:[/bold] [dim]{review_id}[/dim]"
    )
    console.print()

    # Phase 1: Analyze the diff using style, security, and logic specialist agents.
    console.print(
        Rule("[bold blue]Phase 1 · Specialist Agents[/bold blue]", style="white")
    )
    console.print()
    style_report = _run_specialist(review_id, "style", run_style_agent, diff)
    security_report = _run_specialist(review_id, "security", run_security_agent, diff)
    logic_report = _run_specialist(review_id, "logic", run_logic_agent, diff)
    console.print()

    # Phase 2: Retrieve historical review context to maintain consistency.
    console.print(
        Rule("[bold blue]Phase 2 · Repository Memory[/bold blue]", style="white")
    )
    console.print()
    past_decisions = load_repo_memory(repo)
    memory_context = format_memory_context(past_decisions)
    console.print(f"  [dim]{len(past_decisions)} past review(s) loaded[/dim]")
    console.print()

    # Phase 3: Consolidate specialist reports and resolve any conflicts using the critic.
    console.print(
        Rule("[bold blue]Phase 3 · Critic-Refiner Agent[/bold blue]", style="white")
    )
    console.print()
    console.print(
        "  [yellow]→ consolidating findings and resolving conflicts...[/yellow]"
    )
    decision = run_critic_agent(
        style_report, security_report, logic_report, memory_context, repo
    )

    # Update repo memory with the latest key decisions to guide future reviews.
    save_review_decision(
        repo,
        {"verdict": decision.verdict, "key_decisions": decision.key_decisions},
    )
    console.print("  [green]✓ key decisions saved to memory[/green]")
    console.print()

    return decision
