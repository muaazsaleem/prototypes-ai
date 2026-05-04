# ReAct Agent Prototype

Demonstrates the **ReAct (Reasoning + Acting)** pattern: an LLM that interleaves
Thought → Action → Observation cycles to solve tasks using external tools.

## Concept

ReAct lets a model decide *what to think*, *which tool to call*, and *what to infer
from the result* — all in a tight loop. Each cycle is:

```
Thought  →  Action (tool call)  →  Observation (tool result)  →  repeat
```

This prototype shows the ReAct pattern in action:

- **The Task** requires three tools in order (search → calculator → summariser). The
  agent calls them in the right sequence and produces a correct final answer.

The key insight: **ReAct is powerful but needs explicit loop detection and step
budgets**. Without them, a stuck agent runs forever.

## Tools

| Tool | What it does |
|------|-------------|
| `search(query)` | Looks up a small in-memory knowledge base (simulates web search) |
| `calculator(expr)` | Safely evaluates arithmetic expressions via AST (no `eval`) |
| `summariser(text)` | Calls Gemini to compress text into one sentence |

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

## Parameters (top of `main.py`)

| Name | Default | Effect |
|------|---------|--------|
| `MAX_STEPS` | `12` | Hard step budget; agent is halted when reached |
| Loop detection window | `3` | Halts if the same tool+arg appears 3 times in a row |
