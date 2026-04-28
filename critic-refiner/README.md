# Critic-Refiner Loop

A two-agent prototype that shows why critics need structured rubrics.

## What it does

**Agent A (Refiner)** writes a system design for a URL shortener.  
**Agent B (Critic)** evaluates the draft and returns feedback.  
Agent A revises. Repeat for **3 rounds**.

The prototype runs this loop **twice** — once with a rubric, once without — and compares the quality delta.

| | With Rubric | Without Rubric |
|---|---|---|
| Feedback type | Scores per criterion + actionable note | Vague high-level impressions |
| Refiner's target | Concrete ("Fault Tolerance 4/10 — no replication strategy") | Diffuse ("consider adding more detail") |
| Expected result | Measurable improvement each round | Little to no improvement |

## Why this matters

A rubric operationalizes quality. Without one:

- The critic cannot score objectively — every draft feels "pretty good"
- The refiner has no specific gap to close
- Revisions are stylistic, not substantive
- Quality stagnates across rounds

With a rubric, each criterion is a checklist item. Low score → clear action → targeted revision → score rises.

## Rubric used

| Criterion | What it checks |
|---|---|
| API Design | Endpoints defined with methods and request/response formats? |
| Data Storage | Data model and storage technology specified and justified? |
| Scalability | Read/write scaling and caching addressed? |
| Fault Tolerance | Failure modes and replication strategies addressed? |
| Security | Rate limiting, abuse prevention, and auth addressed? |

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

## Output

1. **Experiment 1** — 3 rounds of rubric-guided critique. Each round shows the draft and a scored table per criterion.
2. **Experiment 2** — 3 rounds of vague critique. Each round shows the draft and the unstructured feedback text.
3. **Summary table** — Round 1 vs Round 3 scores for both experiments (scored on the same rubric for fair comparison), plus a verdict on the quality delta.
