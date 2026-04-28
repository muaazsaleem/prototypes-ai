# Checkpoint and Replay

Demonstrates **checkpointing** and **idempotency** in multi-step AI agents.

A 6-step agent designs a URL shortener. After each step it writes a checkpoint to disk. The prototype simulates a mid-run crash, then shows two different outcomes: recovery via checkpoint (zero repeated work) vs. forced restart without one (wasted LLM calls).

---

## The Concept

A multi-step agent builds up state incrementally. Each step depends on the previous step's output. If the agent crashes at step 4, you want to continue from step 4 — not redo steps 1–3.

**Checkpointing** makes this possible:
- After each step succeeds, write `{step_index, inputs, outputs, timestamp}` to disk.
- On restart, load the checkpoint. Skip steps already done. Resume from the next one.
- The invariant: the checkpoint always reflects a **consistent, fully-completed** state.

Without checkpointing, a crash at step 4 discards all prior work. The agent must start over. In production systems with long-running agents and real latency/cost per call, this is the difference between a fragile demo and a recoverable system.

---

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key_here"
```

---

## Demo: With Checkpointing

**Step 1 — Run the agent (it crashes mid-way intentionally):**

```bash
python main.py run
```

The agent completes steps 1–3, saves a checkpoint after each one, then simulates a crash at step 4. The checkpoint file `checkpoint.json` is left on disk.

**Step 2 — Resume from checkpoint:**

```bash
python main.py resume
```

The agent loads `checkpoint.json`, skips steps 1–3 (already done), and continues from step 4. No repeated LLM calls. The summary shows exactly how many steps were recovered for free.

---

## Demo: Without Checkpointing

```bash
python main.py no-checkpoint
```

The agent runs without writing any checkpoint. The same crash fires at step 4. Since there is nothing to recover from, the agent restarts from step 1. Steps 1–3 are called again — marked as `(repeated — wasted work)` in the output.

The final summary shows total LLM calls made vs. minimum needed, and the overhead percentage.

---

## Key Takeaway

| Scenario | Steps 1–3 | After crash |
|---|---|---|
| With checkpoint | Done once, saved | Resume from step 4 |
| Without checkpoint | Done once, lost | Redo from step 1 |

**Checkpointing = idempotency at the step level.** Each step becomes a safe unit of work. The system can always recover to the last consistent state without duplicating completed work.
