#!/usr/bin/env python3
"""
LLM-as-Judge: Positional Bias Exposure

Generates 10 candidate outputs for a fixed task, then judges them 1-5 in four
scenarios: simple prompt with original ordering, simple prompt after swapping
two outputs, rubric prompt with original ordering, rubric prompt after swapping.
Demonstrates that the same content receives different scores depending on where
it sits in the prompt, and that a structured rubric shrinks this gap.
"""

import json
import os
import re
import textwrap
import time

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Model ──────────────────────────────────────────────────────────────────────
MODEL_ID = "gemini-2.5-flash"

# ── Experiment settings ────────────────────────────────────────────────────────
TASK = "Explain what recursion is in one sentence, suitable for a complete beginner."
NUM_OUTPUTS = 10
SWAP_A = 0  # 0-indexed; output at this position moves to SWAP_B's slot
SWAP_B = 5  # 0-indexed; output at this position moves to SWAP_A's slot

# ── Prompts ────────────────────────────────────────────────────────────────────

GENERATION_PROMPT = (
    "Generate a unique one-sentence explanation of recursion for a complete beginner. "
    "Respond with ONLY the explanation sentence — no preamble, no quotation marks. "
    "Use an analogy, metaphor, or concrete example to make it vivid."
)

# Intentionally vague: no scoring criteria, no anchor definitions.
# This maximises the judge's susceptibility to contextual/positional signals.
SIMPLE_JUDGE_PROMPT = """\
You are evaluating {n} candidate responses to this task: "{task}"

Rate each response on a scale of 1-5 for overall quality.
Respond with ONLY a valid JSON array of {n} integers, nothing else.
Example: [3, 4, 2, 5, 3, 4, 4, 2, 3, 5]

Responses:
{responses}"""

# Explicit per-level criteria anchor each score to observable properties,
# leaving less room for the judge to be swayed by position or neighbour quality.
RUBRIC_JUDGE_PROMPT = """\
You are evaluating {n} candidate responses to this task: "{task}"

Score each response INDEPENDENTLY using this rubric:
  5 = Excellent: accurate, uses a helpful analogy or example, immediately clear to a beginner
  4 = Good: accurate and mostly clear, minor improvements possible
  3 = Acceptable: correct but unclear or slightly too technical
  2 = Poor: partially correct, jargon-heavy, or confusing
  1 = Very Poor: incorrect, misleading, or wholly unsuitable

Respond with ONLY a valid JSON array of {n} integers, nothing else.
Example: [3, 4, 2, 5, 3, 4, 4, 2, 3, 5]

Responses:
{responses}"""


# ── Model helpers ──────────────────────────────────────────────────────────────


def setup_model():
    """Create and return a Gemini client using GEMINI_API_KEY from the environment."""
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def call_model(client, prompt, temperature=0.9):
    """Send a single-turn prompt and return the stripped response text.

    temperature=0.0 is used for judging (stable, deterministic scores).
    temperature=1.0 is used for generation (diverse candidate outputs).
    Raises RuntimeError if the model returns an empty response.
    """
    config = types.GenerateContentConfig(temperature=temperature)
    response = client.models.generate_content(
        model=MODEL_ID, contents=prompt, config=config
    )
    if not response.text:
        raise RuntimeError("Empty response from model")
    return response.text.strip()


# ── Rich display helpers ───────────────────────────────────────────────────────


def display_llm_input(messages):
    """Render a list of role/content dicts as a bright_black bordered input panel."""
    elements = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            label_style, content_style = "bold blue", "blue"
        elif role == "assistant":
            label_style, content_style = "bold green", "green"
        else:
            label_style, content_style = "dim", "dim"
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        elements.append(Rule(style="bright_black"))
    if elements:
        elements.pop()  # remove trailing rule
    console.print(
        Panel(
            Group(*elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_llm_response(response_text):
    """Render the raw model response verbatim inside a bright_black bordered panel."""
    wrapped = textwrap.fill(response_text, width=82, subsequent_indent="           ")
    content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))
    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ── Judging logic ──────────────────────────────────────────────────────────────


def format_responses(outputs):
    """Return outputs as a numbered string block for embedding in a judge prompt."""
    return "\n".join(f"Response {i + 1}: {out}" for i, out in enumerate(outputs))


def extract_scores(text, expected_count):
    """Parse the first JSON integer array from model text.

    Uses a regex to locate the array so it survives stray prose or markdown
    fences in the response. Raises ValueError if the array is absent or has
    the wrong number of elements.
    """
    match = re.search(r"\[[\d,\s]+\]", text)
    if not match:
        raise ValueError(f"No JSON array found in response: {text!r}")
    scores = json.loads(match.group())
    if len(scores) != expected_count:
        raise ValueError(f"Expected {expected_count} scores, got {len(scores)}")
    return scores


def run_judge(client, outputs, task, use_rubric, label):
    """Score a list of outputs 1-5 using the LLM as judge.

    Selects the simple or rubric prompt based on use_rubric, displays the
    full LLM input/output panels, and returns a list of integer scores
    in the same order as outputs.
    """
    template = RUBRIC_JUDGE_PROMPT if use_rubric else SIMPLE_JUDGE_PROMPT
    prompt = template.format(
        n=len(outputs), task=task, responses=format_responses(outputs)
    )

    console.print(
        f"[bold cyan]-- {label} --------------------------------------[/bold cyan]"
    )
    display_llm_input([{"role": "user", "content": prompt}])

    # temperature=0 for reproducible, stable scores across repeated runs
    raw = call_model(client, prompt, temperature=0.0)
    display_llm_response(raw)

    return extract_scores(raw, len(outputs))


# ── Analysis helpers ───────────────────────────────────────────────────────────


def align_swapped_scores(scores, pos_a, pos_b):
    """Remap scores from a position-swapped list back to original output indices.

    After the judge scores the swapped list, position pos_a holds the output
    originally at pos_b (and vice versa). Swapping those two score slots undoes
    the reordering so that scores[i] always refers to the original i-th output.
    """
    aligned = list(scores)
    aligned[pos_a], aligned[pos_b] = aligned[pos_b], aligned[pos_a]
    return aligned


def bias_stats(original, aligned_swapped, swap_a, swap_b):
    """Compute per-output score deltas split into swapped vs. non-swapped groups.

    Returns a dict with:
      deltas         - signed score change per output (swapped - original)
      mean_swapped   - mean absolute delta for the two physically moved outputs
      mean_other     - mean absolute delta for outputs that stayed in place
    """
    deltas = [aligned_swapped[i] - original[i] for i in range(len(original))]
    swapped_abs = [abs(deltas[swap_a]), abs(deltas[swap_b])]
    other_abs = [
        abs(deltas[i]) for i in range(len(deltas)) if i not in (swap_a, swap_b)
    ]
    return {
        "deltas": deltas,
        "mean_swapped": sum(swapped_abs) / len(swapped_abs),
        "mean_other": sum(other_abs) / len(other_abs) if other_abs else 0.0,
    }


def print_score_table(original, aligned_swapped, swap_a, swap_b, title):
    """Print original vs. post-swap scores side-by-side with a signed delta column."""
    table = Table(title=title, show_lines=True)
    table.add_column("#", style="bold", justify="center")
    table.add_column("Original Score", justify="center")
    table.add_column("Score After Swap", justify="center")
    table.add_column("Delta", justify="center")
    table.add_column("Note", style="dim")

    for i in range(len(original)):
        orig = original[i]
        swp = aligned_swapped[i]
        delta = swp - orig

        if delta > 0:
            delta_str = f"[green]+{delta}[/green]"
        elif delta < 0:
            delta_str = f"[red]{delta}[/red]"
        else:
            delta_str = "[dim]+/-0[/dim]"

        note = ""
        if i == swap_a:
            note = f"moved pos {swap_a + 1} -> {swap_b + 1}"
        elif i == swap_b:
            note = f"moved pos {swap_b + 1} -> {swap_a + 1}"

        table.add_row(str(i + 1), str(orig), str(swp), delta_str, note)

    console.print(table)
    console.print()


# ── Entry point ────────────────────────────────────────────────────────────────


def main():
    """Orchestrate the three-phase bias experiment and print the final verdict."""
    console.print(
        Panel.fit(
            "[bold yellow]LLM-as-Judge: Positional Bias Exposure[/bold yellow]\n"
            "[dim]Same output, different position in prompt => different score.[/dim]\n"
            f"[dim]{NUM_OUTPUTS} candidate outputs | swapping positions "
            f"{SWAP_A + 1} & {SWAP_B + 1} | model: {MODEL_ID}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    client = setup_model()

    # ── Phase 1: Generate 10 diverse candidate outputs ─────────────────────────
    console.print(
        Rule("[bold]Phase 1 — Generating Candidate Outputs[/bold]", style="white")
    )
    console.print()

    outputs = []
    for i in range(NUM_OUTPUTS):
        t0 = time.time()
        text = call_model(client, GENERATION_PROMPT, temperature=1.0)
        outputs.append(text)
        elapsed = time.time() - t0
        console.print(
            f"  Output #{i + 1:02d}: [green]o[/green] [dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )
        if (i + 1) % 4 == 0:
            console.print()

    console.print()
    console.print()

    console.print(
        "[bold cyan]-- All Candidate Outputs ----------------------------[/bold cyan]"
    )
    for i, out in enumerate(outputs):
        console.print(f"  [bold]{i + 1:2d}.[/bold] {out}")
    console.print()

    # ── Phase 2: Simple prompt judging ────────────────────────────────────────
    console.print(
        Rule("[bold]Phase 2 — Simple Prompt Judging (No Rubric)[/bold]", style="white")
    )
    console.print()

    scores_simple_orig = run_judge(
        client, outputs, TASK, use_rubric=False, label="Simple Judge — Original Order"
    )

    # Build the swapped list: physically exchange the two outputs in the prompt
    swapped = list(outputs)
    swapped[SWAP_A], swapped[SWAP_B] = swapped[SWAP_B], swapped[SWAP_A]

    scores_simple_swapped_raw = run_judge(
        client,
        swapped,
        TASK,
        use_rubric=False,
        label=f"Simple Judge — Swapped Order (pos {SWAP_A + 1}<>{SWAP_B + 1})",
    )
    # Re-align so index i always refers to the same original output
    scores_simple_swapped = align_swapped_scores(
        scores_simple_swapped_raw, SWAP_A, SWAP_B
    )

    print_score_table(
        scores_simple_orig,
        scores_simple_swapped,
        SWAP_A,
        SWAP_B,
        "Simple Prompt — Score Comparison",
    )
    simple_stats = bias_stats(scores_simple_orig, scores_simple_swapped, SWAP_A, SWAP_B)

    # ── Phase 3: Rubric-based judging ─────────────────────────────────────────
    console.print(Rule("[bold]Phase 3 — Rubric-Based Judging[/bold]", style="white"))
    console.print()

    scores_rubric_orig = run_judge(
        client, outputs, TASK, use_rubric=True, label="Rubric Judge — Original Order"
    )

    scores_rubric_swapped_raw = run_judge(
        client,
        swapped,
        TASK,
        use_rubric=True,
        label=f"Rubric Judge — Swapped Order (pos {SWAP_A + 1}<>{SWAP_B + 1})",
    )
    scores_rubric_swapped = align_swapped_scores(
        scores_rubric_swapped_raw, SWAP_A, SWAP_B
    )

    print_score_table(
        scores_rubric_orig,
        scores_rubric_swapped,
        SWAP_A,
        SWAP_B,
        "Rubric Prompt — Score Comparison",
    )
    rubric_stats = bias_stats(scores_rubric_orig, scores_rubric_swapped, SWAP_A, SWAP_B)

    # ── Summary table ─────────────────────────────────────────────────────────
    console.print(
        Rule("[bold yellow]Bias Exposure Summary[/bold yellow]", style="yellow")
    )
    console.print()

    summary = Table(title="Positional Bias: Simple vs Rubric", show_lines=True)
    summary.add_column("Metric", style="bold", min_width=40)
    summary.add_column("Simple Prompt", justify="center")
    summary.add_column("Rubric Prompt", justify="center")
    summary.add_column("Bias Reduction", justify="center")

    def fmt_reduction(r):
        """Format a bias-reduction value: green if positive (bias shrank), red if negative."""
        if r > 0:
            return f"[green]-{r:.2f}[/green]"
        elif r < 0:
            return f"[red]+{abs(r):.2f}[/red]"
        return "[dim]0.00[/dim]"

    ms = simple_stats["mean_swapped"]
    mr = rubric_stats["mean_swapped"]
    os_ = simple_stats["mean_other"]
    or_ = rubric_stats["mean_other"]

    summary.add_row(
        f"Avg |delta| — swapped outputs (pos {SWAP_A + 1}<>{SWAP_B + 1})",
        f"{ms:.2f}",
        f"{mr:.2f}",
        fmt_reduction(ms - mr),
    )
    summary.add_row(
        "Avg |delta| — non-swapped outputs (context noise)",
        f"{os_:.2f}",
        f"{or_:.2f}",
        fmt_reduction(os_ - or_),
    )
    summary.add_section()

    # Per-swapped-output breakdown
    for pos in [SWAP_A, SWAP_B]:
        ds = simple_stats["deltas"][pos]
        dr = rubric_stats["deltas"][pos]
        ds_color = "red" if ds != 0 else "green"
        dr_color = "red" if dr != 0 else "green"
        summary.add_row(
            f"Output {pos + 1} score shift when moved to new position",
            f"[{ds_color}]{ds:+d}[/{ds_color}]",
            f"[{dr_color}]{dr:+d}[/{dr_color}]",
            fmt_reduction(abs(ds) - abs(dr)),
        )

    console.print(summary)
    console.print()

    # ── Verdict ───────────────────────────────────────────────────────────────
    if mr < ms:
        color, verdict = "green", "RUBRIC REDUCES POSITIONAL BIAS"
    elif mr == ms:
        color, verdict = "yellow", "NO CHANGE — BIAS EQUALLY PRESENT IN BOTH"
    else:
        color, verdict = "red", "RUBRIC DID NOT REDUCE BIAS (try re-running)"

    console.print(
        Panel.fit(
            f"[bold {color}]{verdict}[/bold {color}]\n"
            f"[dim]Simple prompt  avg |delta| for swapped outputs: {ms:.2f}[/dim]\n"
            f"[dim]Rubric prompt  avg |delta| for swapped outputs: {mr:.2f}[/dim]",
            border_style=color,
        )
    )
    console.print()


if __name__ == "__main__":
    main()
