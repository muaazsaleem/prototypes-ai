import argparse
import json
import time

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from agent import DiagnosisAgent, RemediationProposal
from alerts import SCENARIOS, Alert
from geval import GEvaluator
from output_filter import OutputFilter
from pagerduty import PagerDuty
from risk_judge import ESCALATION_THRESHOLD, RiskJudge
from tools import execute_remediation_tool

console = Console()


def print_alert(alert: Alert):
    """Renders the incoming alert as a red bordered panel in the terminal."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold", min_width=14)
    table.add_column()
    table.add_row("ID:", alert.id)
    table.add_row("Service:", f"[bold]{alert.service}[/bold]")
    table.add_row("Type:", alert.alert_type)
    table.add_row("Severity:", f"[red bold]{alert.severity.upper()}[/red bold]")
    table.add_row("Description:", alert.description)
    table.add_row("Metadata:", json.dumps(alert.metadata))
    console.print(
        Panel(table, title="[red bold]  ALERT RECEIVED[/red bold]", border_style="red")
    )


def print_proposal(proposal: RemediationProposal):
    """Renders the agent's remediation proposal as a cyan bordered panel."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", min_width=16)
    table.add_column()
    table.add_row("Diagnosis:", proposal.diagnosis)
    table.add_row("Root Cause:", proposal.root_cause)
    table.add_row("Action:", proposal.proposed_action.get("description", ""))
    table.add_row("Tool:", proposal.proposed_action.get("tool", ""))
    table.add_row(
        "Parameters:", json.dumps(proposal.proposed_action.get("parameters", {}))
    )
    table.add_row("Target:", proposal.proposed_action.get("target_service", ""))
    table.add_row("Rollback:", proposal.rollback_plan.get("description", ""))
    table.add_row("Confidence:", f"{proposal.confidence:.0%}")
    console.print(
        Panel(
            table,
            title="[cyan bold]  REMEDIATION PROPOSAL[/cyan bold]",
            border_style="cyan",
        )
    )


def run_pipeline(alert: Alert):
    """Runs the full remediation pipeline for a single alert.

    Steps: ingest → diagnose → output filter → risk score → execute or escalate → G-Eval.
    Returns early after PagerDuty escalation if the output filter blocks the action;
    G-Eval is skipped in that case because no action was attempted.
    """
    console.print(Rule(f"[bold white]{alert.id}  ·  {alert.alert_type}[/bold white]"))
    console.print()

    # ── Step 1: Ingest alert ─────────────────────────────────────────────────
    print_alert(alert)
    console.print()

    # ── Step 2: Agent diagnosis (agentic loop with tool calling) ─────────────
    console.print("[bold yellow]  Diagnosis Agent running...[/bold yellow]")
    agent = DiagnosisAgent()
    proposal = agent.run(alert)
    console.print()
    print_proposal(proposal)
    console.print()

    # ── Step 3: Output filter — is the target service in-scope? ─────────────
    console.print("[bold blue]  Output Filter[/bold blue]")
    output_filter = OutputFilter()
    is_in_scope, filter_reason = output_filter.check(proposal)

    if not is_in_scope:
        # Block and escalate if the service is not allowed to be auto-remediated
        console.print(f"  [red bold]✗ BLOCKED:[/red bold] {filter_reason}")
        console.print()
        PagerDuty().escalate(alert, proposal, f"Output filter: {filter_reason}")
        console.print(
            "\n[dim]  G-Eval skipped — action was blocked before execution.[/dim]\n"
        )
        return

    console.print(f"  [green bold]✓ IN SCOPE:[/green bold] {filter_reason}")
    console.print()

    # ── Step 4: Risk scoring ─────────────────────────────────────────────────
    console.print("[bold magenta]  Risk Judge[/bold magenta]")
    risk_judge = RiskJudge()
    risk_score, risk_reasoning, concerns = risk_judge.score(proposal, alert)

    score_color = (
        "green"
        if risk_score < 0.4
        else "yellow" if risk_score < ESCALATION_THRESHOLD else "red"
    )
    console.print(
        f"  Risk Score:  [{score_color}]{risk_score:.2f}[/{score_color}]  (threshold: {ESCALATION_THRESHOLD})"
    )
    console.print(f"  Reasoning:   [dim]{risk_reasoning}[/dim]")
    if concerns:
        console.print(f"  Concerns:    [dim]{', '.join(concerns)}[/dim]")
    console.print()

    # ── Step 5: Execute or escalate ──────────────────────────────────────────
    if risk_score >= ESCALATION_THRESHOLD:
        # High risk requires human intervention
        console.print("[red]  Risk too high — escalating to PagerDuty.[/red]\n")
        PagerDuty().escalate(
            alert,
            proposal,
            f"Risk score {risk_score:.2f} exceeds threshold {ESCALATION_THRESHOLD}",
        )
        outcome = f"escalated_to_human: risk_score={risk_score:.2f}"
    else:
        # Safe to proceed with automated fix
        action = proposal.proposed_action
        console.print(
            f"[green]  Risk acceptable — auto-executing:[/green] {action['description']}"
        )

        result = execute_remediation_tool(action["tool"], action.get("parameters", {}))
        console.print(f"  [green]✓ {result.get('message', 'Done')}[/green]")
        console.print(
            f"  [dim]Rollback ready: {proposal.rollback_plan['description']}[/dim]"
        )
        outcome = f"executed_successfully: {result.get('message', '')}"

    console.print()

    # ── Step 6: G-Eval — score quality and save to fine-tuning dataset ───────
    console.print("[bold]  G-Eval: scoring remediation quality[/bold]\n")
    GEvaluator().evaluate(alert, proposal, outcome)
    console.print()


def main():
    """Parses CLI args and runs one or all demo scenarios in sequence."""
    parser = argparse.ArgumentParser(
        description="Incident Auto-Remediation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                          # run all 4 scenarios\n"
            "  python main.py --scenario cpu_spike     # low risk → auto-execute\n"
            "  python main.py --scenario payment_errors # out-of-scope → PagerDuty\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        help="Run a single scenario (default: all four in sequence)",
    )
    args = parser.parse_args()

    # Main application header
    console.print(
        Panel.fit(
            "[bold yellow]Incident Auto-Remediation Agent[/bold yellow]\n"
            "[dim]Alert → Diagnose → Filter → Risk Score → Execute / Escalate → G-Eval[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    scenarios = (
        [SCENARIOS[args.scenario]] if args.scenario else list(SCENARIOS.values())
    )

    for i, alert in enumerate(scenarios):
        run_pipeline(alert)
        # Brief pause between scenarios so the terminal output is easier to follow
        if i < len(scenarios) - 1:
            time.sleep(1)


if __name__ == "__main__":
    main()
