#!/usr/bin/env python3
"""
Prompt Regression Harness
=========================
Concept: Prompts are code. They need tests. Changes have consequences.

This harness:
  1. Defines two versions of a prompt (v1 = baseline, v2 = "improved")
  2. Runs 10 test cases against each version
  3. Shows a pass/fail comparison table that highlights regressions and fixes
"""

import json
import os
import time
import textwrap

from google import genai

# ─── Prompt Versions ──────────────────────────────────────────────────────────
#
# Both prompts classify a customer support message into urgency + category.
#
# v2 adds one "reasonable-sounding" rule — watch which tests break.

PROMPT_V1 = textwrap.dedent("""\
    You are a customer support triage assistant.
    Classify the incoming customer message and return ONLY valid JSON.
    No markdown, no explanation — raw JSON only.

    Output format:
      {"urgency": "LOW|MEDIUM|HIGH", "category": "billing|technical|general"}

    Urgency levels:
      HIGH   — service outage, data loss, security breach, or active revenue loss
      MEDIUM — degraded experience, partial failure, time-sensitive non-critical request
      LOW    — general questions, feature requests, or compliments

    Categories:
      billing   — charges, payments, invoices, refunds, or subscription changes
      technical — product bugs, errors, performance problems
      general   — everything else
""")

PROMPT_V2 = textwrap.dedent("""\
    You are a customer support triage assistant.
    Classify the incoming customer message and return ONLY valid JSON.
    No markdown, no explanation — raw JSON only.

    Output format:
      {"urgency": "LOW|MEDIUM|HIGH", "category": "billing|technical|general"}

    Urgency levels:
      HIGH   — service outage, data loss, security breach, or active revenue loss
      MEDIUM — degraded experience, partial failure, time-sensitive non-critical request
      LOW    — general questions, feature requests, or compliments

    Categories:
      billing   — charges, payments, invoices, refunds, or subscription changes
      technical — product bugs, errors, performance problems
      general   — everything else

    Additional rule: To improve security and developer support, any message
    mentioning 'API', 'token', 'webhook', 'password', or 'login' MUST be
    classified as HIGH urgency and 'technical', regardless of the context.
""")

# ─── Test Suite ───────────────────────────────────────────────────────────────
#
# 10 test cases covering all urgency levels and categories.
# expected = the ground-truth label we want the prompt to produce every time.

TEST_CASES = [
    {
        "id": 1,
        "input": "My entire team cannot log in since this morning. We have a client deadline today.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 2,
        "input": "How do I change my profile picture?",
        "expected": {"urgency": "LOW", "category": "general"},
    },
    {
        "id": 3,
        "input": "I need a copy of my invoice from last month for my accounting team.",
        "expected": {"urgency": "LOW", "category": "billing"},
    },
    {
        "id": 4,
        "input": "Where can I find the API token for my personal hobby project?",
        "expected": {"urgency": "LOW", "category": "technical"},
    },
    {
        "id": 5,
        "input": "I'm getting 500 errors on the checkout page and losing sales right now.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 6,
        "input": "Can you send me the link to your REST API documentation?",
        "expected": {"urgency": "LOW", "category": "technical"},
    },
    {
        "id": 7,
        "input": "The mobile app is noticeably slow when scrolling through my feed.",
        "expected": {"urgency": "MEDIUM", "category": "technical"},
    },
    {
        "id": 8,
        "input": "I'd like to update my password for security, where is the setting?",
        "expected": {"urgency": "LOW", "category": "general"},
    },
    {
        "id": 9,
        "input": "I found a critical bug where webhook validation can be bypassed.",
        "expected": {"urgency": "HIGH", "category": "technical"},
    },
    {
        "id": 10,
        "input": "Can I get a refund for my recent payment? I didn't mean to renew.",
        "expected": {"urgency": "MEDIUM", "category": "billing"},
    },
]

# ─── Core Harness ─────────────────────────────────────────────────────────────

def classify(client: genai.Client, prompt: str, message: str) -> dict:
    """Call Gemini with the system prompt + user message, return parsed JSON."""
    full_prompt = f"{prompt}\nCustomer message:\n{message}"
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=full_prompt,
    )
    text = response.text.strip()
    # Strip markdown code fences the model sometimes adds
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def check(actual: dict, expected: dict) -> tuple[bool, str]:
    """Compare actual vs expected on every field. Return (passed, failure_reason)."""
    for field in ("urgency", "category"):
        if actual.get(field) != expected[field]:
            return False, f"{field}: expected '{expected[field]}', got '{actual.get(field)}'"
    return True, ""


def run_suite(client: genai.Client, prompt: str, label: str) -> list[dict]:
    """Run every test case against the prompt. Return a list of result dicts."""
    print(f"\nRunning {label} ({len(TEST_CASES)} tests)...")
    results = []
    for tc in TEST_CASES:
        try:
            actual = classify(client, prompt, tc["input"])
            passed, reason = check(actual, tc["expected"])
        except Exception as exc:
            actual = {}
            passed, reason = False, f"exception: {exc}"

        marker = "✓" if passed else "✗"
        print(f"  [{marker}] #{tc['id']:02d}  {tc['input'][:60]}...")
        results.append({
            "id":       tc["id"],
            "input":    tc["input"],
            "expected": tc["expected"],
            "actual":   actual,
            "passed":   passed,
            "reason":   reason,
        })
        time.sleep(0.5)  # stay within free-tier rate limits
    return results


# ─── Reporting ────────────────────────────────────────────────────────────────

def show_prompt_diff() -> None:
    """Print lines added in v2 that weren't in v1 — makes the change visible."""
    v1_lines = set(PROMPT_V1.splitlines())
    added   = [l for l in PROMPT_V2.splitlines() if l not in v1_lines and l.strip()]
    removed = [l for l in PROMPT_V1.splitlines() if l not in set(PROMPT_V2.splitlines()) and l.strip()]

    print("\nPrompt diff  (V1 → V2):")
    for line in removed:
        print(f"  - {line}")
    for line in added:
        print(f"  + {line}")


def render_table(v1_results: list[dict], v2_results: list[dict]) -> None:
    """Print a side-by-side pass/fail comparison table and regression summary."""
    INPUT_W  = 48
    STATUS_W = 8

    row_fmt = "| {:>2} | {:<{iw}} | {:^{sw}} | {:^{sw}} | {:^12} |"
    divider = (
        "+" + "-" * 4
        + "+" + "-" * (INPUT_W + 2)
        + "+" + "-" * (STATUS_W + 2)
        + "+" + "-" * (STATUS_W + 2)
        + "+" + "-" * 14
        + "+"
    )

    print("\n" + "=" * len(divider))
    print("  REGRESSION REPORT")
    print("=" * len(divider))
    print(divider)
    print(row_fmt.format(
        "#", "Customer Message",
        "V1", "V2", "Delta",
        iw=INPUT_W, sw=STATUS_W,
    ))
    print(divider)

    v2_by_id = {r["id"]: r for r in v2_results}
    regressions, fixes = [], []

    for r1 in v1_results:
        r2      = v2_by_id[r1["id"]]
        snippet = (r1["input"][:INPUT_W - 3] + "...") if len(r1["input"]) > INPUT_W else r1["input"]
        s1      = "PASS" if r1["passed"] else "FAIL"
        s2      = "PASS" if r2["passed"] else "FAIL"

        if r1["passed"] and not r2["passed"]:
            delta = "REGRESSED ✗"
            regressions.append((r1, r2))
        elif not r1["passed"] and r2["passed"]:
            delta = "FIXED ✓"
            fixes.append((r1, r2))
        else:
            delta = "same"

        print(row_fmt.format(
            r1["id"], snippet, s1, s2, delta,
            iw=INPUT_W, sw=STATUS_W,
        ))

    print(divider)

    total   = len(v1_results)
    v1_pass = sum(1 for r in v1_results if r["passed"])
    v2_pass = sum(1 for r in v2_results if r["passed"])

    print(f"\nSummary:")
    print(f"  Prompt V1 : {v1_pass}/{total} passed")
    print(f"  Prompt V2 : {v2_pass}/{total} passed")
    print(f"  Regressions (V1 PASS → V2 FAIL) : {len(regressions)}")
    print(f"  Fixes       (V1 FAIL → V2 PASS) : {len(fixes)}")

    if regressions:
        print("\nRegression details:")
        for r1, r2 in regressions:
            print(f"\n  #{r1['id']:02d}  \"{r1['input']}\"")
            print(f"       expected : {r1['expected']}")
            print(f"       v1 got   : {r1['actual']}  ← PASS")
            print(f"       v2 got   : {r2['actual']}  ← {r2['reason']}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Error: GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    show_prompt_diff()

    v1_results = run_suite(client, PROMPT_V1, label="Prompt V1 (baseline)")
    v2_results = run_suite(client, PROMPT_V2, label="Prompt V2 (+billing rule)")

    render_table(v1_results, v2_results)


if __name__ == "__main__":
    main()
