import json
import os
import textwrap
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agent import RemediationProposal
from alerts import Alert

console = Console()

DATASET_FILE = Path("remediation_dataset.jsonl")

# G-Eval criteria: name, weight in final score, what to evaluate, and the rubric.
# Weights are chosen so diagnosis + action account for 65% (most important for fine-tuning).
EVAL_CRITERIA = [
    {
        "name": "Diagnosis Accuracy",
        "weight": 0.35,
        "description": "Does the diagnosis correctly identify the problem based on the alert symptoms?",
        "rubric": (
            "1=Wrong diagnosis, "
            "2=Partially correct but missing key evidence, "
            "3=Correct but vague, "
            "4=Correct and specific with supporting evidence, "
            "5=Perfectly identifies root cause with clear evidence chain"
        ),
    },
    {
        "name": "Action Relevance",
        "weight": 0.30,
        "description": "Is the proposed action the right fix for the diagnosed problem?",
        "rubric": (
            "1=Wrong action entirely, "
            "2=Tangentially related but ineffective, "
            "3=Correct action type but wrong parameters, "
            "4=Correct action and well-targeted, "
            "5=Optimal action with precise parameters"
        ),
    },
    {
        "name": "Safety",
        "weight": 0.20,
        "description": "Does the remediation minimize blast radius and include a viable rollback?",
        "rubric": (
            "1=Dangerous (no rollback, wide blast radius), "
            "2=Risky with inadequate rollback, "
            "3=Acceptable risk with basic rollback, "
            "4=Safe with clear rollback plan, "
            "5=Minimal blast radius with solid, tested rollback path"
        ),
    },
    {
        "name": "Completeness",
        "weight": 0.15,
        "description": "Is the proposal complete: diagnosis, action, parameters, and rollback all present?",
        "rubric": (
            "1=Missing multiple key fields, "
            "2=Incomplete, missing rollback or parameters, "
            "3=Basic coverage, "
            "4=All fields present and reasonable, "
            "5=Thorough with all details and edge cases considered"
        ),
    },
]

SYSTEM_PROMPT = """You are an expert SRE evaluator assessing incident remediation quality.

For the given criterion, think step-by-step before scoring.
This chain-of-thought reasoning is important — it makes the score auditable.

Respond ONLY with JSON:
{
  "criterion": "criterion name",
  "reasoning": "your step-by-step reasoning (2-4 sentences)",
  "score": 3
}
Score must be an integer 1–5.
"""


class GEvaluator:
    """
    G-Eval: LLM-as-judge with chain-of-thought scoring.
    Evaluates a remediation against four criteria and saves the result
    as a JSONL dataset entry that can be used for fine-tuning.
    """

    def __init__(self):
        """Initialises the Gemini client used for all per-criterion LLM calls."""
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def evaluate(
        self, alert: Alert, proposal: RemediationProposal, outcome: str
    ) -> dict:
        """Scores the remediation against all criteria and returns scores, reasoning, and final_score.

        Makes one LLM call per criterion (4 total), computes a weighted average,
        normalises to [0, 1], prints the table to the terminal, and appends a JSONL
        entry to DATASET_FILE for fine-tuning.
        """
        scores = {}
        reasoning = {}

        for criterion in EVAL_CRITERIA:
            score, reason = self._score_criterion(criterion, alert, proposal, outcome)
            scores[criterion["name"]] = score
            reasoning[criterion["name"]] = reason

        # Weighted average across criteria, then normalize from [1,5] to [0,1]
        weighted_raw = sum(scores[c["name"]] * c["weight"] for c in EVAL_CRITERIA)
        final_score = round((weighted_raw - 1) / 4, 3)  # maps [1,5] → [0,1]

        self._print_scores(scores, reasoning, final_score)
        self._save_to_dataset(alert, proposal, outcome, scores, final_score)

        return {"scores": scores, "reasoning": reasoning, "final_score": final_score}

    def _score_criterion(
        self,
        criterion: dict,
        alert: Alert,
        proposal: RemediationProposal,
        outcome: str,
    ) -> tuple[int, str]:
        """Calls the LLM evaluator for one criterion and returns (score 1–5, reasoning text)."""
        prompt = (
            f"CRITERION: {criterion['name']}\n"
            f"WHAT TO EVALUATE: {criterion['description']}\n"
            f"RUBRIC: {criterion['rubric']}\n\n"
            f"INCIDENT DETAILS:\n"
            f"Alert: {alert.description}\n"
            f"Diagnosis: {proposal.diagnosis}\n"
            f"Root Cause: {proposal.root_cause}\n"
            f"Action Taken: {json.dumps(proposal.proposed_action)}\n"
            f"Rollback Plan: {json.dumps(proposal.rollback_plan)}\n"
            f"Outcome: {outcome}\n\n"
            f"Evaluate this criterion and provide your score."
        )

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
        return int(result["score"]), result["reasoning"]

    def _parse_response(self, text: str) -> dict:
        """Strips markdown fences and parses the evaluator's JSON response."""
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

    def _print_scores(self, scores: dict, reasoning: dict, final_score: float):
        """Renders the per-criterion scores and final weighted score as a rich table."""
        table = Table(title="G-Eval Scores", show_lines=True)
        table.add_column("Criterion", style="cyan", min_width=20)
        table.add_column("Score", justify="center", style="bold", min_width=8)
        table.add_column("Reasoning", style="dim")

        for criterion in EVAL_CRITERIA:
            name = criterion["name"]
            score = scores[name]
            # Color coding based on score severity
            color = "green" if score >= 4 else "yellow" if score >= 3 else "red"
            snippet = reasoning[name]
            # Truncate reasoning to prevent table blowout
            if len(snippet) > 130:
                snippet = snippet[:127] + "..."
            table.add_row(name, f"[{color}]{score}/5[/{color}]", snippet)

        console.print(table)

        # Map final score to human-readable colors
        score_color = (
            "green" if final_score >= 0.7 else "yellow" if final_score >= 0.5 else "red"
        )
        console.print(
            f"\n[bold]Final G-Eval Score:[/bold] [{score_color}]{final_score:.3f}[/{score_color}]"
            f"  [dim](entry appended to {DATASET_FILE})[/dim]"
        )

    def _save_to_dataset(
        self,
        alert: Alert,
        proposal: RemediationProposal,
        outcome: str,
        scores: dict,
        final_score: float,
    ):
        """Appends one JSONL record to DATASET_FILE; each record is a self-contained training example."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "alert": {
                "id": alert.id,
                "service": alert.service,
                "type": alert.alert_type,
                "description": alert.description,
                "metadata": alert.metadata,
            },
            "diagnosis": proposal.diagnosis,
            "root_cause": proposal.root_cause,
            "action": proposal.proposed_action,
            "rollback": proposal.rollback_plan,
            "confidence": proposal.confidence,
            "outcome": outcome,
            "geval_scores": scores,
            "final_score": final_score,
        }

        with open(DATASET_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
