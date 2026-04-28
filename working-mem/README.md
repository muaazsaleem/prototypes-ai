# Working Memory: Context Overflow & Memory Management

Demonstrates that **context is finite** and **memory management is an engineering problem**, not a prompt problem.

An AI agent reviews a 10-step database migration plan. At each step it receives new tool output and must remember everything it has seen. The prototype runs the same task twice:

- **Phase 1 — Naive agent**: appends every turn verbatim. Context grows without bound.
- **Phase 2 — Managed agent**: after step 5, compresses completed steps into a dense bullet-point memory block and continues with the smaller context.

At the end of both phases, the agent is asked to recall a specific fact from Step 1 (exact rollback command + time window). The naive agent fails once its early context is dropped; the managed agent succeeds because the summary preserved the fact.

## Concept

| | Naive | Managed |
|---|---|---|
| Context growth | Linear — every token stays forever | Bounded — old turns replaced by a summary |
| Token cost at step 10 | High | Significantly lower |
| Step-1 recall after overflow | **LOST** | **RETAINED** |

The key insight: the model did not forget because it was "bad at remembering". It forgot because the tokens were physically absent from the context window. The fix is not a better prompt — it is an engineering step (summarisation) that keeps critical facts alive in a compressed form.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python3 main.py
```

Expected runtime: ~2–3 minutes (makes ~25 Gemini API calls).

## Output

- Step-by-step token bars for both phases, highlighted red when over budget
- Inline compression stats (tokens before → after, % saved)
- Three verification results showing what is retained vs lost
- Final comparison table across all 10 steps
