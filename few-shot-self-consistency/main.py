#!/usr/bin/env python3
"""
Prototype: Few-Shot with Self-Consistency
=========================================
Concept: Self-consistency is a cheap accuracy boost before you reach for fine-tuning.

Three progressive stages on a sentiment classification task:
  Stage 1 – Zero-shot      : no examples, deterministic (temp=0)
  Stage 2 – Few-shot       : 3 labelled examples in the prompt, deterministic
  Stage 3 – Self-consistency: few-shot repeated 5× with temp=0.7, majority vote wins
"""

import os
import sys
import textwrap
import collections
import time

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-2.5-flash"
SC_RUNS = 5  # how many times to sample for self-consistency
SC_TEMP = 0.7  # temperature used during self-consistency sampling
VALID_LABELS = {"positive", "negative", "neutral"}

# ── Few-shot examples (deliberately kept OUT of the test set) ─────────────────
# These three examples are injected into the prompt to ground the model.
FEW_SHOT_EXAMPLES = [
    ("I absolutely loved this product! Best purchase of the year.", "positive"),
    ("Completely useless. Broke after two days. Total waste of money.", "negative"),
    ("Package arrived on time. Contents match the description.", "neutral"),
]

# ── Test set ──────────────────────────────────────────────────────────────────
# Mix of easy cases and deliberately ambiguous ones.
# The ambiguous ones are where zero-shot struggles and self-consistency helps most.
TEST_SET = [
    # easy ───────────────────────────────────────────────────────────────────
    ("Fast shipping and amazing quality. I am genuinely thrilled!", "positive"),
    ("Horrible customer service. They completely ignored my complaint.", "negative"),
    ("The item looks exactly like the photos on the website.", "neutral"),
    ("Five stars. Will order again without hesitation.", "positive"),
    ("This is the worst thing I have ever bought. Returning immediately.", "negative"),
    # tricky / ambiguous ─────────────────────────────────────────────────────
    ("It is fine, I guess. Does exactly what it says on the box.", "neutral"),
    ("Not the best, not the worst. Pretty average overall.", "neutral"),
    ("I am a bit disappointed by the size, but the quality is good.", "negative"),
    ("Surprisingly decent for such a low price point.", "positive"),
    ("Great product, but the packaging was absolutely terrible.", "negative"),
    ("It works. That is honestly all I can say about it.", "neutral"),
    ("I would recommend it only to someone with very low expectations.", "negative"),
    ("Better than I expected, but still far from impressive.", "neutral"),
    ("The colour is slightly off, but everything else is perfect.", "neutral"),
    ("Solid product. Nothing special, nothing broken. Does the job.", "neutral"),
]


# ── Prompt builders ───────────────────────────────────────────────────────────


def zero_shot_prompt(text: str) -> str:
    """Returns a zero-shot prompt for sentiment classification.

    Accepts the review text and wraps it in a prompt that asks for a one-word
    sentiment classification (positive, negative, or neutral).
    """
    return f"""\
Classify the sentiment of the review as exactly one word: positive, negative, or neutral.

Review: {text}
Sentiment:"""


def few_shot_prompt(text: str) -> str:
    """Returns a few-shot prompt for sentiment classification.

    Injects FEW_SHOT_EXAMPLES into the prompt before the target review text
    to ground the model in the expected output format and labels.
    """
    examples = "\n".join(
        f"Review: {ex_text}\nSentiment: {ex_label}"
        for ex_text, ex_label in FEW_SHOT_EXAMPLES
    )
    return f"""\
Classify the sentiment of the review as exactly one word: positive, negative, or neutral.

{examples}

Review: {text}
Sentiment:"""


# ── Model call ────────────────────────────────────────────────────────────────


def call_model(client: genai.Client, prompt: str, temperature: float) -> str:
    """Send a prompt to Gemini and return the cleaned label.

    Handles API errors gracefully and attempts to normalize the model output
    into one of the VALID_LABELS. Returns 'unknown' if no valid label is found.
    """
    try:
        # Display model input
        input_elements = [
            Text.assemble(("USER: ", "bold blue"), (prompt, "blue")),
            Rule(style="bright_black"),
        ]
        console.print(
            Panel(
                Group(*input_elements),
                title="[bold bright_black]Model Input[/bold bright_black]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=1024,  # Increased to allow for 'thinking' tokens
            ),
        )

        # Display model response
        if response and response.text:
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

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] API Error: {e}")
        return "unknown"

    if not response or not response.text:
        return "unknown"

    # Clean and normalize
    text = response.text.lower().strip()

    # Check each word for a valid label
    for word in text.split():
        clean = word.strip(".,!?*`_:")
        if clean in VALID_LABELS:
            return clean

    # Final fallback search
    for label in VALID_LABELS:
        if label in text:
            return label

    return "unknown"


# ── Classification strategies ─────────────────────────────────────────────────


def zero_shot(client: genai.Client, text: str) -> str:
    """Performs sentiment classification using a zero-shot prompt.

    Uses temperature 0.0 for deterministic results.
    """
    return call_model(client, zero_shot_prompt(text), temperature=0.0)


def few_shot(client: genai.Client, text: str) -> str:
    """Performs sentiment classification using a few-shot prompt.

    Uses temperature 0.0 for deterministic results.
    """
    return call_model(client, few_shot_prompt(text), temperature=0.0)


def self_consistent(client: genai.Client, text: str) -> tuple[str, list[str]]:
    """Sample the few-shot prompt SC_RUNS times at SC_TEMP.

    Returns a tuple of (majority_vote, list_of_all_votes).
    Majority voting provides a reliability boost by sampling multiple paths.
    """
    votes = [
        call_model(client, few_shot_prompt(text), temperature=SC_TEMP)
        for _ in range(SC_RUNS)
    ]
    winner = collections.Counter(votes).most_common(1)[0][0]
    return winner, votes


# ── Display helpers ───────────────────────────────────────────────────────────


def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Render a colored progress bar for accuracy metrics.

    Uses green for >= 80%, yellow for >= 50%, and red otherwise.
    """
    pct = correct / total
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def print_stage(
    title: str,
    predictions: list[str],
    votes_list: list[list[str]] | None = None,
) -> float:
    """Print a formatted results table and return accuracy.

    Uses a Rich Table to display predictions against ground truth labels.
    """
    console.print(Rule(f"[bold]{title}[/bold]", style="white"))

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("No.", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Review Text", min_width=40)
    table.add_column("True Label")
    table.add_column("Prediction")
    if votes_list:
        table.add_column("Votes")

    correct = 0
    for i, ((text, true_label), pred) in enumerate(zip(TEST_SET, predictions), 1):
        hit = pred == true_label
        correct += hit
        mark = "[bold green]✓[/bold green]" if hit else "[bold red]✗[/bold red]"
        short = textwrap.shorten(text, width=40, placeholder="…")

        row = [str(i), mark, short, true_label, pred]
        if votes_list:
            row.append(", ".join(votes_list[i - 1]))
        table.add_row(*row)

    console.print(table)

    accuracy = correct / len(TEST_SET)
    console.print(f"\n  Accuracy: {accuracy_bar(correct, len(TEST_SET))}")
    console.print()
    return accuracy


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    """Main execution loop for the Few-Shot and Self-Consistency prototype.

    Iterates through zero-shot, few-shot, and self-consistency stages,
    reporting accuracy and improvements for each.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] set the GEMINI_API_KEY environment variable."
        )
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    console.print(
        Panel.fit(
            "[bold yellow]Few-Shot with Self-Consistency — Sentiment Classification[/bold yellow]\n"
            f"[dim]Model: {MODEL_NAME} | Samples: {len(TEST_SET)}[/dim]\n"
            f"[dim]SC runs: {SC_RUNS} × temperature={SC_TEMP}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    console.print("[bold cyan]Few-shot examples injected into the prompt:[/bold cyan]")
    for text, label in FEW_SHOT_EXAMPLES:
        short = textwrap.shorten(text, width=50, placeholder="…")
        console.print(f"  [{label}] {short}")
    console.print()

    # ── Stage 1: Zero-shot ────────────────────────────────────────────────────
    console.print(
        "[bold cyan]-- [1/3] Running zero-shot ... ----------------[/bold cyan]"
    )
    zs_preds = [zero_shot(client, text) for text, _ in TEST_SET]
    zs_acc = print_stage("STAGE 1 — ZERO-SHOT (no examples, temp=0)", zs_preds)

    # ── Stage 2: Few-shot ─────────────────────────────────────────────────────
    console.print(
        "[bold cyan]-- [2/3] Running few-shot ... -----------------[/bold cyan]"
    )
    fs_preds = [few_shot(client, text) for text, _ in TEST_SET]
    fs_acc = print_stage("STAGE 2 — FEW-SHOT (3 examples, temp=0)", fs_preds)

    # ── Stage 3: Self-consistency ─────────────────────────────────────────────
    console.print(
        f"[bold cyan]-- [3/3] Running self-consistency ({SC_RUNS} samples) ... --[/bold cyan]"
    )
    sc_results = [self_consistent(client, text) for text, _ in TEST_SET]
    sc_preds = [pred for pred, _ in sc_results]
    sc_votes = [votes for _, votes in sc_results]
    sc_acc = print_stage(
        f"STAGE 3 — SELF-CONSISTENCY (few-shot ×{SC_RUNS}, temp={SC_TEMP})",
        sc_preds,
        sc_votes,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))

    summary_table = Table(show_header=True, header_style="bold", show_lines=True)
    summary_table.add_column("Strategy")
    summary_table.add_column("Accuracy")
    summary_table.add_column("Lift vs Zero-shot")

    def lift_str(new_acc, old_acc):
        lift = new_acc - old_acc
        if lift > 0:
            return f"[bold green]+{lift:.1%}[/bold green]"
        elif lift < 0:
            return f"[bold red]{lift:.1%}[/bold red]"
        return "[dim]±0%[/dim]"

    summary_table.add_row("Zero-shot", f"{zs_acc:.1%}", "-")
    summary_table.add_row("Few-shot", f"{fs_acc:.1%}", lift_str(fs_acc, zs_acc))
    summary_table.add_row("Self-consistency", f"{sc_acc:.1%}", lift_str(sc_acc, zs_acc))

    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    main()
