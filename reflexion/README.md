# Reflexion Prototype

Demonstrates **Reflexion** — in-session self-improvement where an AI agent reflects on its own failures and uses those reflections to do better on the next attempt.

## Concept

Reflexion is a prompting pattern where, after each failed attempt, the agent writes a short "reflection note" — a diagnosis of what went wrong and what to do differently. That note is fed back in as context for the next attempt, compounding within the run.

**Key insight:** Reflexion is in-session learning. It compounds within a single run, but resets completely between runs. There is no persistent memory across sessions.

## What This Prototype Does

The agent is given a coding task: implement `merge_intervals(intervals)`, a classic algorithm with well-known edge cases (touching intervals, unsorted input, containment).

Across 3 attempts:
1. **Attempt 1** — cold start, no context
2. **Attempt 2** — receives the reflection note from attempt 1
3. **Attempt 3** — receives both prior reflection notes

After each attempt, results are evaluated against 8 test cases. Scores are shown across all attempts so you can see whether Reflexion improved the output.

## Why This Task

Merge intervals has enough edge cases (touching boundaries, unsorted input, deep containment) that first attempts often miss 2–3 tests. This makes the improvement arc from Reflexion clearly visible and measurable.

## Setup

```bash
pip install -r requirements.txt
```

Set your Gemini API key:

```bash
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

## Expected Output

- Per-attempt test results (PASS / FAIL per case)
- Score progress bar
- Failure breakdown with expected vs. got
- Reflection note written by the agent after each non-final attempt
- Final summary table comparing scores across all 3 attempts
- Verdict: improved / no change / regressed
