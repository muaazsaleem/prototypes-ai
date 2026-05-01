# Coding Agent — ReAct + Reflexion

An autonomous coding agent that fixes bugs in a codebase by running a **ReAct loop** (Reason → Act → Observe) with a **Reflexion** layer that learns from test failures across retries.

---

## How it works

```
For each attempt (up to --max-iter):
  1. Build prompt   ← task + working memory + past reflections
  2. ReAct loop     ← model calls tools: list_files, read_file, write_file, run_tests, ...
  3. Verify         ← framework independently runs the test suite
  4. Reflexion      ← on failure, model diagnoses what went wrong → stored in memory
  5. Retry or escalate
```

**ReAct** — the model reasons in natural language, then acts by calling a tool, then observes the result, repeating until it decides it is done.

**Reflexion** — instead of retrying blindly, the agent is asked to diagnose the failure, and that diagnosis is injected into the next attempt's prompt as working memory.

**Working memory** — tracks which files have been read and modified, plus all past reflections, so the model never loses context across attempts.

---

## Project structure

```
agent-coding/
├── main.py       # CLI entry point
├── agent.py      # CodingAgent — ReAct loop + Reflexion
├── tools.py      # Tool implementations + Gemini tool registry
├── memory.py     # WorkingMemory dataclass
├── demo/
│   ├── calculator.py       # Buggy source file (2 intentional bugs)
│   └── test_calculator.py  # Pytest suite that drives the agent
└── requirements.txt
```

---

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key-here"
```

---

## Run

**Fix the demo repo (2 bugs in calculator.py):**

```bash
python main.py "Fix all failing tests" --repo ./demo
```

**Point at any repo:**

```bash
python main.py "Fix the failing tests" --repo /path/to/your/repo
```

**Options:**

```
python main.py --help

positional arguments:
  task            Natural language description of what the agent should do

options:
  --repo PATH     Path to the repository root (default: current directory)
  --max-iter N    Maximum ReAct + Reflexion iterations before escalating (default: 5)
```

---

## What the demo does

`demo/calculator.py` has two intentional bugs:

```python
def subtract(a, b):
    return a + b   # bug: should be a - b

def divide(a, b):
    return a * b   # bug: should be a / b
```

`demo/test_calculator.py` has tests that catch both bugs. The agent will:

1. List the files to understand the repo
2. Read the test file to learn what is expected
3. Read `calculator.py` to spot the bugs
4. Write the fixed file
5. Run the linter, then the tests
6. Report success when all tests pass

Exit code `0` = success, `1` = escalated (tests still failing after max iterations).
