import json
import os
import textwrap

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from agent import RemediationProposal
from alerts import Alert

console = Console()

# Threshold above which we don't auto-execute — human must approve.
ESCALATION_THRESHOLD = 0.65

SYSTEM_PROMPT = """You are a risk assessment judge for infrastructure automation.

Evaluate the risk of executing the proposed remediation action. Consider:
- Blast radius: how many users or downstream services are affected?
- Reversibility: can we easily undo this action?
- Confidence: is the diagnosis well-supported by the collected evidence?
- Service criticality: is this a core revenue-generating or auth service?
- Action severity: scale-up < restart < kill-queries < rollback < schema change

Risk score guide:
  0.0–0.3  Safe to auto-execute (scale up, clear cache, minor config)
  0.3–0.6  Caution but acceptable (service restart with fast rollback available)
  0.6–0.8  High risk — human approval recommended (rollback, multi-service impact)
  0.8–1.0  Critical risk — always escalate (production DB writes, payment infra)

Respond ONLY with JSON:
{
  "risk_score": 0.0,
  "reasoning": "concise explanation of the score",
  "key_concerns": ["concern1", "concern2"]
}
"""


class RiskJudge:
    """Scores the risk of a proposed remediation action using an LLM judge."""

    def __init__(self):
        """Initialises the Gemini client for the risk-scoring judge."""
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def score(
        self, proposal: RemediationProposal, alert: Alert
    ) -> tuple[float, str, list[str]]:
        """Calls the LLM judge and returns (risk_score, reasoning, key_concerns).

        risk_score is a float in [0, 1]; scores at or above ESCALATION_THRESHOLD
        should be routed to a human instead of auto-executed.
        """
        prompt = self._build_prompt(proposal, alert)

        # --- Style Model Input ---
        input_elements = []
        # System instructions
        indent = " " * 8
        wrapped_sys = textwrap.fill(SYSTEM_PROMPT, width=82, subsequent_indent=indent)
        input_elements.append(Text.assemble(("SYSTEM: ", "dim"), (wrapped_sys, "dim")))
        input_elements.append(Rule(style="bright_black"))
        # User prompt
        indent = " " * 6
        wrapped_user = textwrap.fill(prompt, width=82, subsequent_indent=indent)
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

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )

        # --- Style Model Response ---
        wrapped_response = textwrap.fill(
            response.text, width=82, subsequent_indent="           "
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

        result = self._parse_response(response.text)
        return (
            float(result["risk_score"]),
            result["reasoning"],
            result.get("key_concerns", []),
        )

    def _build_prompt(self, proposal: RemediationProposal, alert: Alert) -> str:
        """Assembles the judge prompt with all context the model needs to score risk accurately."""
        return (
            f"Alert: {alert.description}\n"
            f"Diagnosis: {proposal.diagnosis}\n"
            f"Root Cause: {proposal.root_cause}\n"
            f"Agent Confidence: {proposal.confidence}\n"
            f"Proposed Action: {json.dumps(proposal.proposed_action, indent=2)}\n"
            f"Rollback Plan: {json.dumps(proposal.rollback_plan, indent=2)}\n\n"
            f"Assess the risk of executing this action."
        )

    def _parse_response(self, text: str) -> dict:
        """Strips markdown fences and parses the judge's JSON response."""
        # Clean up common markdown formatting if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        text = text.strip()
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1:
                text = text[start:end]

        return json.loads(text)
