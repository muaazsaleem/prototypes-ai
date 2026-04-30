# Latency Budget Breakdown

**Concept:** You cannot optimize what you have not measured. P95 matters more than P50 in production.

## What This Demonstrates

A three-step AI pipeline is instrumented end-to-end:

1. **retrieve** — simulates a vector-database lookup (I/O-bound, random latency)
2. **validate** — a lightweight Gemini call that checks query safety and relevance (a guard-rail step, independent of retrieval)
3. **generate** — the main Gemini call that produces a grounded answer using the retrieved docs

The prototype runs both modes across 20 requests and computes **P50, P95, and P99** per step.

### Why P95 over P50?

P50 (median) tells you what the average user sees. P95 tells you what 1 in 20 users sees — and in any system handling real traffic, that tail is what drives user complaints, SLA breaches, and on-call pages. Mean is even worse: a handful of slow outliers pull it up and hide the real distribution.

### Sequential vs Parallel

In the sequential mode the pipeline runs strictly left-to-right: `retrieve → validate → generate`.

`retrieve` and `validate` have **no data dependency** on each other — retrieve fetches documents while validate checks the query text, and neither needs the other's output. This makes them safe to parallelize with `asyncio.gather`. After parallelization the effective wall-clock time for the first phase becomes `max(retrieve, validate)` instead of `retrieve + validate`.

`generate` always runs last because it needs both outputs, so it stays on the critical path and becomes the new bottleneck.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

The script prints:
- Live LLM input/output panels for run #1 of each phase (as a demonstration)
- Progress dots for runs 2–20
- Per-step latency tables (P50 / P95 / P99 / mean) for both phases
- A comparison summary showing speedup and time saved
- Saves `latency_breakdown.png` — a 4-panel chart with step percentiles, distributions, total comparison, and speedup factors

## Output

```
latency_breakdown.png   — matplotlib chart (4 panels)
```

## Model

Uses `gemini-2.5-flash`. To change the model, edit the `MODEL` constant at the top of `main.py`.
