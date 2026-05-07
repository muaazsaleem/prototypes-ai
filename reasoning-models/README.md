# Adaptive Effort Agent

An agent that routes each step to a different Gemini **thinking budget** based on the step type — demonstrating how production AI agents can control cost and latency by allocating reasoning effort selectively.

## The concept

Gemini 2.5 Flash supports a configurable `thinking_budget`: the maximum number of tokens the model can spend on internal chain-of-thought reasoning before producing its answer. Setting the budget to `0` disables thinking entirely.

This prototype maps three agent step types to three effort levels:

| Step type   | Effort | `thinking_budget` | When to use |
|-------------|--------|-------------------|-------------|
| `plan`      | HIGH   | 8192              | Ambiguous, multi-step reasoning tasks |
| `debug`     | MEDIUM | 2048              | Focused problem-solving with known context |
| `read file` | ZERO   | 0                 | Retrieval / summarisation — no reasoning needed |

The agent runs six demo steps (two of each type), then prints per-step token counts and a summary table showing average thinking tokens, latency, and total cost per step type.

## Prerequisites

- Python 3.11+
- `GEMINI_API_KEY` set in your environment

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## What to look at in the output

1. **Thinking tokens per step** — `plan` steps consume far more thinking tokens than `debug`, and `read file` steps consume none.
2. **Cost column** — thinking tokens are priced at ~46× the rate of output tokens, so the cost difference between effort levels is dramatic even for small token counts.
3. **Summary table** — aggregates across step types so you can see the cost-vs-effort trade-off at a glance.
4. **Cost ratio verdict** — the final line shows how many times more expensive `HIGH` effort is vs `ZERO` effort across the run.

## Pricing

Costs use approximate Gemini 2.5 Flash rates defined in `PRICING` at the top of `main.py`. Update those constants if the official rates change.

| Token type | Rate (USD / 1M tokens) |
|------------|------------------------|
| Input      | $0.075                 |
| Output     | $0.300                 |
| Thinking   | $3.500                 |
