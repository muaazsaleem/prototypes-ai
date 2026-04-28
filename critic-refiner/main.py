#!/usr/bin/env python3
"""
Critic-Refiner Loop Prototype

Two-agent system:
  - Agent A (Refiner): produces and revises a system design document
  - Agent B (Critic): evaluates the draft and returns structured feedback

Experiment 1 — Critic WITH a structured rubric:
  Each criterion has a precise bar. The refiner gets targeted scores and
  actionable improvement notes. Run for 3 rounds; quality rises measurably.

Experiment 2 — Critic WITHOUT a rubric:
  The critic gives vague, high-level impressions. The refiner has no target.
  Revisions are directionless; quality barely moves.

The final table scores both experiments using the same rubric so the
quality delta is directly comparable.
"""

import json
import os
import re
import textwrap

from google import genai
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Gemini client ──────────────────────────────────────────────────────────────
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# ── Shared task ────────────────────────────────────────────────────────────────
# Both experiments use the same task so results are comparable.
TASK = (
    "Write a concise system design for a URL shortener service. "
    "Cover: API endpoints, data storage, scalability, fault tolerance, and security. "
    "Use bullet points and short sections. Aim for ~300 words."
)

# ── Structured rubric ──────────────────────────────────────────────────────────
# Each criterion names a specific, measurable bar — the critic can score it
# objectively and the refiner knows exactly what "better" means.
RUBRIC = {
    "API Design": (
        "Are endpoints clearly defined with HTTP methods and request/response formats?"
    ),
    "Data Storage": (
        "Is the data model specified? Is storage technology chosen and justified?"
    ),
    "Scalability": (
        "Are read/write scaling strategies addressed? Is caching mentioned?"
    ),
    "Fault Tolerance": (
        "Are failure modes and redundancy/replication strategies addressed?"
    ),
    "Security": ("Are rate limiting, abuse prevention, and authentication addressed?"),
}

CRITERIA = list(RUBRIC.keys())
ROUNDS = 3


# ── LLM helper ─────────────────────────────────────────────────────────────────


def log_llm_interaction(prompt: str, response_text: str) -> None:
    """Log the LLM interaction in a human-readable, styled format."""
    # Input Block
    console.print(Rule("[bold blue]Model Input[/bold blue]", style="blue"))
    label = "[bold blue]user[/bold blue]"
    wrapped = textwrap.fill(prompt, width=88, subsequent_indent="         ")
    console.print(f"  {label}:    [blue]{wrapped}[/blue]")
    console.print()

    # Output Block
    console.print(Rule("[bold green]Model Response[/bold green]", style="green"))
    console.print(f"[italic]{response_text}[/italic]", highlight=False)
    console.print()


def call_model(prompt: str) -> str:
    """Send a plain-text prompt to Gemini and return the response."""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    response_text = response.text.strip()
    log_llm_interaction(prompt, response_text)
    return response_text


# ── Agent A: Refiner ───────────────────────────────────────────────────────────


def refiner_initial_draft() -> str:
    """Produce a first draft with no prior feedback."""
    prompt = f"You are a software architect. {TASK}"
    return call_model(prompt)


def refiner_revise(draft: str, feedback: str) -> str:
    """Produce a revised draft that addresses every feedback point."""
    prompt = (
        "You are a software architect. You wrote the following system design:\n\n"
        f"{draft}\n\n"
        "You received this feedback:\n\n"
        f"{feedback}\n\n"
        "Revise the design to specifically address every feedback point. "
        "Add concrete detail where scores or comments indicate a gap. "
        "Aim for ~300 words."
    )
    return call_model(prompt)


# ── Agent B: Critic — WITH rubric ──────────────────────────────────────────────


def critic_with_rubric(draft: str) -> dict:
    """
    Evaluate the draft against the structured rubric.
    Returns {criterion: {score: int, feedback: str}} for each criterion.
    Scores are 1–10 integers; feedback is one actionable sentence.
    """
    rubric_lines = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    # Provide an explicit JSON schema so the model returns parseable output.
    schema_lines = ",\n".join(
        f'  "{k}": {{"score": <1-10 integer>, "feedback": "<one sentence>"}}'
        for k in CRITERIA
    )
    prompt = (
        "You are a senior systems architect reviewing a design document.\n\n"
        f"Rubric (score each criterion 1–10):\n{rubric_lines}\n\n"
        f"Design to evaluate:\n{draft}\n\n"
        "Respond ONLY with valid JSON — no markdown fences, no extra text:\n"
        f"{{\n{schema_lines}\n}}"
    )
    raw = call_model(prompt)
    # Strip markdown fences if the model adds them anyway
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def critique_to_feedback_text(critique: dict) -> str:
    """Format a structured critique dict into readable text for Agent A."""
    return "\n".join(
        f"[{k}] Score {v['score']}/10 — {v['feedback']}" for k, v in critique.items()
    )


# ── Agent B: Critic — WITHOUT rubric ──────────────────────────────────────────


def critic_no_rubric(draft: str) -> str:
    """
    Give vague, high-level feedback with no rubric and no scoring.
    This is what a critic does without a structured evaluation framework —
    impressions rather than measurements.
    """
    prompt = (
        "You are a reviewer. Read this design and give some general thoughts "
        "on how it could be improved. Keep it brief and high-level.\n\n"
        f"Design:\n{draft}"
    )
    return call_model(prompt)


# ── Scoring helpers ────────────────────────────────────────────────────────────


def overall_score(critique: dict) -> float:
    """Average score across all rubric criteria (1–10 scale)."""
    return sum(v["score"] for v in critique.values()) / len(critique)


def score_color(score: float) -> str:
    """Map a 1–10 score to a semantic rich color."""
    if score >= 8:
        return "green"
    elif score >= 6:
        return "yellow"
    return "red"


# ── Display helpers ────────────────────────────────────────────────────────────


def print_draft(round_num: int, draft: str) -> None:
    console.print(f"[bold cyan]-- Draft (Round {round_num}) {'─' * 40}[/bold cyan]")
    wrapped = textwrap.fill(draft, width=92, subsequent_indent="  ")
    console.print(f"  [dim]{wrapped}[/dim]")
    console.print()


def print_rubric_critique(round_num: int, critique: dict) -> None:
    console.print(
        f"[bold magenta]-- Critique (Round {round_num}) {'─' * 38}[/bold magenta]"
    )
    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Criterion", style="bold", min_width=16)
    table.add_column("Score", justify="center", min_width=8)
    table.add_column("Feedback", style="dim")
    for criterion, result in critique.items():
        s = result["score"]
        c = score_color(s)
        table.add_row(criterion, f"[{c}]{s}/10[/{c}]", result["feedback"])
    table.add_section()
    avg = overall_score(critique)
    ac = score_color(avg)
    table.add_row("[bold]Overall[/bold]", f"[bold {ac}]{avg:.1f}/10[/bold {ac}]", "")
    console.print(table)
    console.print()


def print_vague_critique(round_num: int, feedback: str) -> None:
    console.print(
        f"[bold magenta]-- Critique (Round {round_num}) {'─' * 38}[/bold magenta]"
    )
    wrapped = textwrap.fill(feedback, width=92, subsequent_indent="  ")
    console.print(f"  [italic dim]{wrapped}[/italic dim]")
    console.print()


# ── Experiments ────────────────────────────────────────────────────────────────


def experiment_with_rubric() -> list[dict]:
    """
    3 rounds of Refiner → Critic (with rubric) → Refiner.
    The critic returns structured scores; the refiner has a concrete target.
    Returns the list of per-round critique dicts for later comparison.
    """
    console.print(
        Rule(
            "[bold]Experiment 1 — Critic WITH Structured Rubric[/bold]",
            style="white",
        )
    )
    console.print()

    critiques: list[dict] = []

    console.print("[dim]Generating initial draft…[/dim]")
    draft = refiner_initial_draft()
    print_draft(1, draft)

    for rnd in range(1, ROUNDS + 1):
        console.print(f"[dim]Critic scoring round {rnd}…[/dim]")
        critique = critic_with_rubric(draft)
        critiques.append(critique)
        print_rubric_critique(rnd, critique)

        if rnd < ROUNDS:
            # Convert scores + feedback into text the refiner can act on
            feedback = critique_to_feedback_text(critique)
            console.print(f"[dim]Refiner revising for round {rnd + 1}…[/dim]")
            draft = refiner_revise(draft, feedback)
            print_draft(rnd + 1, draft)

    return critiques


def experiment_no_rubric() -> tuple[str, str]:
    """
    3 rounds of Refiner → Critic (no rubric) → Refiner.
    The critic gives vague impressions; the refiner has no measurable target.
    Returns (round-1 draft, round-3 draft) so we can score them externally.
    """
    console.print(
        Rule(
            "[bold]Experiment 2 — Critic WITHOUT Rubric (Vague Feedback)[/bold]",
            style="white",
        )
    )
    console.print()

    first_draft: str = ""
    draft: str = ""

    console.print("[dim]Generating initial draft…[/dim]")
    draft = refiner_initial_draft()
    first_draft = draft
    print_draft(1, draft)

    for rnd in range(1, ROUNDS + 1):
        console.print(f"[dim]Critic evaluating round {rnd}…[/dim]")
        feedback = critic_no_rubric(draft)
        print_vague_critique(rnd, feedback)

        if rnd < ROUNDS:
            console.print(f"[dim]Refiner revising for round {rnd + 1}…[/dim]")
            draft = refiner_revise(draft, feedback)
            print_draft(rnd + 1, draft)

    return first_draft, draft  # (round-1 draft, round-3 draft)


# ── Summary ────────────────────────────────────────────────────────────────────


def print_summary(
    rubric_critiques: list[dict],
    nr_r1_scores: dict,
    nr_r3_scores: dict,
) -> None:
    """
    Print the quality delta table comparing both experiments.
    Both are scored using the same rubric so the numbers are comparable.
    """
    console.print(
        Rule(
            "[bold yellow]Quality Delta — Round 1 → Round 3[/bold yellow]",
            style="yellow",
        )
    )
    console.print()

    r1 = rubric_critiques[0]  # rubric experiment: round-1 scores
    r3 = rubric_critiques[-1]  # rubric experiment: round-3 scores

    table = Table(title="With Rubric vs Without Rubric", show_lines=True)
    table.add_column("Criterion", style="bold", min_width=16)
    table.add_column("Rubric R1", justify="center")
    table.add_column("Rubric R3", justify="center")
    table.add_column("Rubric Δ", justify="center")
    table.add_column("No-Rubric R1", justify="center")
    table.add_column("No-Rubric R3", justify="center")
    table.add_column("No-Rubric Δ", justify="center")

    def fmt_score(s: int) -> str:
        c = score_color(s)
        return f"[{c}]{s}/10[/{c}]"

    def fmt_delta(d: int) -> str:
        if d > 0:
            return f"[green]+{d}[/green]"
        elif d < 0:
            return f"[red]{d}[/red]"
        return "[dim]0[/dim]"

    for criterion in CRITERIA:
        rs1 = r1[criterion]["score"]
        rs3 = r3[criterion]["score"]
        ns1 = nr_r1_scores[criterion]["score"]
        ns3 = nr_r3_scores[criterion]["score"]
        table.add_row(
            criterion,
            fmt_score(rs1),
            fmt_score(rs3),
            fmt_delta(rs3 - rs1),
            fmt_score(ns1),
            fmt_score(ns3),
            fmt_delta(ns3 - ns1),
        )

    # Totals row
    table.add_section()
    ro1 = overall_score(r1)
    ro3 = overall_score(r3)
    no1 = overall_score(nr_r1_scores)
    no3 = overall_score(nr_r3_scores)

    def fmt_avg(s: float) -> str:
        c = score_color(s)
        return f"[bold {c}]{s:.1f}/10[/bold {c}]"

    def fmt_avg_delta(d: float) -> str:
        if d > 0.05:
            return f"[bold green]+{d:.1f}[/bold green]"
        elif d < -0.05:
            return f"[bold red]{d:.1f}[/bold red]"
        return "[bold dim]~0[/bold dim]"

    table.add_row(
        "[bold]Overall[/bold]",
        fmt_avg(ro1),
        fmt_avg(ro3),
        fmt_avg_delta(ro3 - ro1),
        fmt_avg(no1),
        fmt_avg(no3),
        fmt_avg_delta(no3 - no1),
    )
    console.print(table)
    console.print()

    # Verdict
    rubric_lift = ro3 - ro1
    no_rubric_lift = no3 - no1

    console.print(Rule("[bold]Verdict[/bold]", style="white"))
    console.print()

    rubric_label = (
        "[green]clear improvement[/green]"
        if rubric_lift > 1
        else "[yellow]marginal[/yellow]"
    )
    no_rubric_label = (
        "[red]stagnant[/red]"
        if abs(no_rubric_lift) <= 1.0
        else "[yellow]some improvement[/yellow]"
    )

    sign_r = "+" if rubric_lift >= 0 else ""
    sign_n = "+" if no_rubric_lift >= 0 else ""

    console.print(
        f"  With rubric:    [bold]{sign_r}{rubric_lift:.1f} pts[/bold]  {rubric_label}"
    )
    console.print(
        f"  Without rubric: [bold]{sign_n}{no_rubric_lift:.1f} pts[/bold]  {no_rubric_label}"
    )
    console.print()


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    console.print(
        Panel.fit(
            "[bold yellow]Critic-Refiner Loop[/bold yellow]\n"
            "[dim]Agent A drafts · Agent B critiques · Agent A revises[/dim]\n"
            "[dim]3 rounds × 2 experiments  (with rubric | without rubric)[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Experiment 1: critic has a structured rubric
    rubric_critiques = experiment_with_rubric()

    # Experiment 2: critic has no rubric
    nr_draft_r1, nr_draft_r3 = experiment_no_rubric()

    # Score both no-rubric drafts with the rubric critic for a fair comparison
    console.print("[dim]Scoring no-rubric drafts against rubric for comparison…[/dim]")
    nr_r1_scores = critic_with_rubric(nr_draft_r1)
    nr_r3_scores = critic_with_rubric(nr_draft_r3)
    console.print()

    print_summary(rubric_critiques, nr_r1_scores, nr_r3_scores)


if __name__ == "__main__":
    main()
