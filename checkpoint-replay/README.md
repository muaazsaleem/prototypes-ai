# Resumable AI Agent

A production-ready template for building **multi-step AI agents** that can survive crashes, network failures, or manual interruptions with perfect state recovery.

---

## The Core Philosophy: Deep State Recovery

Most "resumable" systems only save the last known progress marker. This agent implements a **Full State Snapshot** pattern, ensuring that when an agent resumes, it doesn't just know *where* it was, but exactly *what* it was thinking.

### 1. Comprehensive Checkpointing
Instead of a simple progress flag, every successful step triggers a full dump to `checkpoint.json` containing:
- **Full History**: Every prompt sent and every response received for all previous steps.
- **Metadata**: Model configuration, task definitions, and precise timestamps.
- **Contextual Integrity**: The exact "memory" of the agent at the moment of the save.

### 2. Full State Recovery
On resumption, the agent performs a **Deep Restore**:
1. It loads the **entire conversation history** back into memory.
2. It reconstructs the **cumulative context** from every single previous turn.
3. It passes this complete context to the LLM for the next step.

This ensures that Step 6 has full access to the constraints defined in Step 1, even if a crash occurred in between.

---

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key_here"
```

---

## Usage

### 1. Run the Agent
```bash
python main.py
```
The agent will start working through the architectural design. You can **interrupt it at any time** (Ctrl+C) to simulate a failure.

### 2. Resume with Perfect Memory
```bash
python main.py
```
Run the same command. The agent will:
- Detect the `checkpoint.json`.
- Restore the full history of previous responses.
- Pick up the next step with the **exact same context** it would have had during a continuous run.

### 3. Reset State
```bash
python main.py --reset
```
Wipes the checkpoint and starts a fresh design from scratch.

---

## Design Trade-offs: Snapshot vs. Incremental

When designing an agentic system, you must choose between two primary checkpointing patterns. This template uses the **Full State Snapshot** pattern.

### Pattern A: Full State Snapshot (Used here)
*At every step, write the entire history and metadata into a single file.*
- **Pros:** 
    - **Atomic Consistency**: The marker (Step 4 done) and the data (History for 1-4) are always perfectly in sync.
    - **Simplicity**: Loading state is a single `json.load()` call. No complex "merging" of history fragments.
    - **Auditability**: You can open the JSON and see the agent's entire "brain" in one place.
- **Cons:** 
    - **I/O Overhead**: The file grows larger with every step.
    - **Scalability**: For agents with thousands of turns or massive token contexts, writing the full history every time becomes inefficient.
- **Best For:** Most enterprise agents, RAG workflows, and multi-step reasoning tasks (6–100 steps).

### Pattern B: Incremental / Append-Only Checkpointing
*Every step writes only its own delta (Prompt/Response) to a log or database.*
- **Pros:** 
    - **High Efficiency**: I/O is constant regardless of how long the agent has been running.
    - **Scalability**: Perfect for long-lived agents that run for days or have massive histories.
- **Cons:** 
    - **Complexity**: Resumption requires "replaying" the entire log to reconstruct the current memory.
    - **Fragmentation Risk**: If the marker updates but the log entry fails, you end up with "state amnesia."
- **Best For:** Social bots, perpetual research agents, and systems with extremely high turn counts.

---

## Why this matters for Engineers

- **Contextual Continuity**: Long-running agents often fail because they lose the "thread" of the conversation after a restart. This pattern prevents "contextual amnesia."
- **Auditability**: The `checkpoint.json` acts as a full audit trail of the agent's reasoning process.
- **Idempotency**: Each step is a guaranteed unit of work. If it's in the checkpoint, it's done—forever.
- **Cost Efficiency**: Never pay for the same expensive LLM reasoning steps twice.
