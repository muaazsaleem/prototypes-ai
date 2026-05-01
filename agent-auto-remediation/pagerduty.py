from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent import RemediationProposal
from alerts import Alert

console = Console()


class PagerDuty:
    """Mock PagerDuty escalation. In production this would call the PagerDuty Events API."""

    def escalate(self, alert: Alert, proposal: RemediationProposal, reason: str) -> str:
        """Prints a formatted PagerDuty incident panel and returns the generated incident ID.

        reason explains why automated remediation was blocked — either output filter or
        risk score above threshold — and is surfaced to the on-call engineer.
        """
        incident_id = f"PD-{alert.id.upper()}-{datetime.now().strftime('%H%M%S')}"

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold yellow", min_width=20)
        table.add_column()
        table.add_row("Incident ID:", incident_id)
        table.add_row("Triggered At:", datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Alert:", alert.description)
        table.add_row("Service:", alert.service)
        table.add_row("Severity:", f"[red]{alert.severity.upper()}[/red]")
        table.add_row("Diagnosis:", proposal.diagnosis)
        table.add_row(
            "Proposed Action:", proposal.proposed_action.get("description", "")
        )
        table.add_row("Blocked Because:", reason)
        table.add_row("Assigned To:", "oncall-sre@company.com")

        console.print(
            Panel(
                table,
                title="[red bold]  PAGERDUTY INCIDENT CREATED[/red bold]",
                border_style="red",
            )
        )
        console.print("[red]  → SMS + call dispatched to on-call engineer[/red]")
        console.print("[red]  → #incidents Slack channel notified[/red]")
        console.print(
            f"[dim]  → Runbook: https://wiki.internal/runbooks/{alert.alert_type.lower()}[/dim]"
        )

        return incident_id
