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

from google import genai
from google.genai import types

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME   = "gemini-2.5-flash"
SC_RUNS      = 5    # how many times to sample for self-consistency
SC_TEMP      = 0.7  # temperature used during self-consistency sampling
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
    return f"""\
Classify the sentiment of the review as exactly one word: positive, negative, or neutral.

Review: {text}
Sentiment:"""


def few_shot_prompt(text: str) -> str:
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
    """Send a prompt to Gemini and return the cleaned label."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=1024, # Increased to allow for 'thinking' tokens
            ),
        )
    except Exception as e:
        print(f"DEBUG: API Error: {e}")
        return "unknown"

    if not response or not response.text:
        print(f"DEBUG: Resposne: ", response)
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

    print(f"DEBUG: Model returned unrecognized text: '{response.text}'")
    return "unknown"


# ── Classification strategies ─────────────────────────────────────────────────

def zero_shot(client: genai.Client, text: str) -> str:
    return call_model(client, zero_shot_prompt(text), temperature=0.0)


def few_shot(client: genai.Client, text: str) -> str:
    return call_model(client, few_shot_prompt(text), temperature=0.0)


def self_consistent(client: genai.Client, text: str) -> tuple[str, list[str]]:
    """
    Sample the few-shot prompt SC_RUNS times at SC_TEMP.
    Return (majority_vote, list_of_all_votes).

    The intuition: if the model is confident, all votes agree.
    If it is uncertain, the majority still tends to be correct.
    """
    votes = [
        call_model(client, few_shot_prompt(text), temperature=SC_TEMP)
        for _ in range(SC_RUNS)
    ]
    winner = collections.Counter(votes).most_common(1)[0][0]
    return winner, votes


# ── Display helpers ───────────────────────────────────────────────────────────

def print_stage(
    title: str,
    predictions: list[str],
    votes_list: list[list[str]] | None = None,
) -> float:
    """Print a formatted results table and return accuracy."""
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")

    correct = 0
    for i, ((text, true_label), pred) in enumerate(zip(TEST_SET, predictions), 1):
        hit = pred == true_label
        correct += hit
        mark  = "✓" if hit else "✗"
        short = textwrap.shorten(text, width=40, placeholder="…")
        print(f"  {i:>2}. [{mark}] {short:<42}  true={true_label:<10} pred={pred}")
        if votes_list:
            print(f"        votes → {votes_list[i - 1]}")

    accuracy = correct / len(TEST_SET)
    print(f"\n  Accuracy: {accuracy:.1%}  ({correct}/{len(TEST_SET)})")
    return accuracy


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Error: set the GEMINI_API_KEY environment variable first.")

    client = genai.Client(api_key=api_key)

    print("=" * 64)
    print("  Few-Shot with Self-Consistency — Sentiment Classification")
    print("=" * 64)
    print(f"  Model   : {MODEL_NAME}")
    print(f"  Samples : {len(TEST_SET)}")
    print(f"  SC runs : {SC_RUNS} × temperature={SC_TEMP}")
    print()
    print("  Few-shot examples injected into the prompt:")
    for text, label in FEW_SHOT_EXAMPLES:
        short = textwrap.shorten(text, width=50, placeholder="…")
        print(f"    [{label}] {short}")

    # ── Stage 1: Zero-shot ────────────────────────────────────────────────────
    print("\n[1/3] Running zero-shot …", flush=True)
    zs_preds = [zero_shot(client, text) for text, _ in TEST_SET]
    zs_acc = print_stage("STAGE 1 — ZERO-SHOT  (no examples, temp=0)", zs_preds)

    # ── Stage 2: Few-shot ─────────────────────────────────────────────────────
    print("\n[2/3] Running few-shot …", flush=True)
    fs_preds = [few_shot(client, text) for text, _ in TEST_SET]
    fs_acc = print_stage("STAGE 2 — FEW-SHOT  (3 examples, temp=0)", fs_preds)

    # ── Stage 3: Self-consistency ─────────────────────────────────────────────
    print(f"\n[3/3] Running self-consistency ({SC_RUNS} samples per review) …", flush=True)
    sc_results = [self_consistent(client, text) for text, _ in TEST_SET]
    sc_preds   = [pred  for pred, _     in sc_results]
    sc_votes   = [votes for _,    votes in sc_results]
    sc_acc = print_stage(
        f"STAGE 3 — SELF-CONSISTENCY  (few-shot ×{SC_RUNS}, temp={SC_TEMP}, majority vote)",
        sc_preds,
        sc_votes,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═' * 64}")
    print(f"  ACCURACY SUMMARY")
    print(f"{'═' * 64}")
    print(f"  Zero-shot         : {zs_acc:.1%}")
    print(f"  Few-shot          : {fs_acc:.1%}   ({fs_acc - zs_acc:+.1%} vs zero-shot)")
    print(f"  Self-consistency  : {sc_acc:.1%}   ({sc_acc - fs_acc:+.1%} vs few-shot  |  {sc_acc - zs_acc:+.1%} vs zero-shot)")
    print(f"{'═' * 64}")
    print()


if __name__ == "__main__":
    main()
