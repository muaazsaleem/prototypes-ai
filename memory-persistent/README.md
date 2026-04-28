# Memory That Persists Across Sessions

Demonstrates the difference between **ephemeral in-context memory** and **persistent external memory** in LLM agents.

## Concept

Every LLM has in-context memory — the messages list you pass on each call. That memory is local to a single session. The moment a new session begins, the messages list is empty and the model has no recollection of anything said before.

External memory is just a data store (here, a JSON file) that you write to after each turn and read from at the start of each turn. Because the file lives on disk, it survives across sessions. The agent itself has no special powers — you are the one retrieving facts and injecting them into the system prompt.

**Key insight:** in-context memory is ephemeral by design. Persistence requires an explicit write strategy and an explicit retrieval strategy.

## What the Prototype Does

Two agents run the same script:

| | Session 1 | Session 2 |
|---|---|---|
| **No-memory agent** | 3-turn chat, user shares name / language / project | New session, no history → blank slate |
| **Memory agent** | Same 3-turn chat + extracts facts → `memory_store.json` | New session, reads file, retrieves by keyword → answers correctly |

After both agents finish their two sessions, a verdict table compares session-2 responses side by side and prints retention stats.

### Memory write strategy
After each turn in session 1, the agent asks the model to extract structured facts as JSON:
```json
[{"keywords": ["name", "user"], "fact": "The user's name is Alex."}]
```

### Memory retrieval strategy
At the start of each turn, the user message is tokenized (stop words stripped). Any stored fact whose `keywords` list overlaps with those tokens is retrieved and injected into the system prompt.

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

The file `memory_store.json` is created during the run and deleted at the start of each run so the demo is always repeatable.
