# Parallel Tool Calls with Partial Failure

Concept: Parallel tool calls are fast but require explicit handling for partial failures.

## What it demonstrates

The model is given three tools and asked for a complete investment briefing on a stock ticker:

| Tool | Behaviour |
| --- | --- |
| `get_stock_price` | Returns price and market metrics (works) |
| `get_analyst_ratings` | Silently returns `{}` -- simulated partial failure |
| `get_recent_news` | Returns latest headlines (works) |

### Two phases

Phase 1 -- No validation

The empty `{}` is passed straight to the model. The model has no explicit signal that the tool failed. It may either:

- Acknowledge missing data (modern models often do this correctly)
- Hallucinate analyst details from training data (less capable or more aggressive models)

Either way, there is no guarantee -- the behaviour is model-dependent and non-deterministic.

Phase 2 -- With validation

A validation layer detects the empty result and replaces it with an explicit error:

```
{"error": "Tool 'get_analyst_ratings' returned no data. Do not estimate or infer this information."}
```

The model is now forced to acknowledge missing data. Correct behaviour is guaranteed regardless of model capability.

### Secondary effect: parallelism

The prototype also tracks how many tool calls happen in each round:

- Phase 1 (silent empty): the model often probes tools sequentially across multiple rounds -- it cannot plan ahead because it does not know what data is available. Total latency is higher.
- Phase 2 (explicit error): the model issues all three tool calls in a single parallel round -- the explicit error in the declaration lets it reason about availability upfront. Total latency is lower.

This is the core trade-off: silent partial failures not only risk hallucination, they also kill the latency benefit of parallel tool calls.

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

## Sample output

```
Phase 1 -- NO VALIDATION
  Tool call rounds              : 3
  Tools in first round (parallel): 1
  Total tool calls              : 3
  First-call latency            : 2.10s
  Total latency                 : 8.65s
  VERDICT: NO HALLUCINATION DETECTED (but not guaranteed)

Phase 2 -- WITH VALIDATION
  Tool call rounds              : 1
  Tools in first round (parallel): 3
  Total tool calls              : 3
  First-call latency            : 1.93s
  Total latency                 : 5.26s
  VERDICT: NO HALLUCINATION DETECTED (guaranteed by validation)

VERDICT: MODEL HANDLED EMPTY GRACEFULLY IN BOTH -- VALIDATION STILL GUARANTEES IT
```

The withheld analyst data is printed at the end to show what the model could have hallucinated (38 buy ratings, $1050 average target, "Strong Buy" consensus).
