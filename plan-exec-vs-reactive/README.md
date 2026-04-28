# Plan-and-Execute vs ReAct Agent

Compares two agentic architectures on the same procurement task to demonstrate the core trade-off:
**planning reduces steps but introduces brittleness**.

## What it demonstrates

| | ReAct | Plan-and-Execute |
|---|---|---|
| Decision-making | One step at a time, full context | Upfront plan, rigid execution |
| OOS handling | Pivots to `search_alternatives` on the fly | Cannot — not in the plan |
| Tool calls | More (exploratory) | Fewer (directed) |
| Outcome | Correct total | Incomplete total (whiteboard silently skipped) |

The mock catalog has a whiteboard that is **intentionally OUT OF STOCK**.  
The Plan-and-Execute agent generates its plan under the optimistic assumption that all items
are available, so it includes no OOS-handling step. When the whiteboard comes back OOS during
execution, the step executor literally cannot search for alternatives — that tool was never
provisioned by the plan. The result is a silent, incomplete calculation.

ReAct has `search_alternatives` available at every step and pivots the moment it sees OOS.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

## What to watch in the output

1. **ReAct section** — observe the tool call sequence. After hitting OOS on `whiteboard`,
   it calls `search_alternatives`, picks the cheapest in-stock substitute, then calculates
   the correct total.

2. **Plan-and-Execute section** — observe the generated plan (no OOS step). During execution,
   one step reports OOS but cannot recover. The calculate step silently skips the whiteboard,
   producing a wrong total.

3. **Summary table** — both agents hit the same number of OOS turns (wrong turns = 1), but
   only ReAct recovered. The difference is in *adaptability*, not in encountering the problem.

## Changing the model

The default model is `gemini-2.0-flash`. To use a different model, change the `MODEL` constant
at the top of `main.py`:

```python
MODEL = "gemini-1.5-flash"   # older, broadly available
MODEL = "gemini-2.0-flash"   # default
```
