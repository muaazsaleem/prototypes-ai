# OpenTelemetry Trace for an Agent Run

Instruments a multi-step ReAct agent with [Langfuse](https://langfuse.com) tracing. Runs one successful trace and one failed trace, prints a span-level comparison table, and identifies the slowest span.

**Concept:** Without tracing, debugging a multi-step agent is guesswork. A trace turns guesswork into a directed investigation — you can see exactly which step was slow, which tool failed, and how much each LLM call cost.

---

## What it demonstrates

- **Root span** (`agent-run`) wrapping the entire agent session
- **Generation spans** for every LLM call — model name, token counts, cost in USD
- **Tool spans** for every tool invocation — tool name, step index, duration, success/failure
- **Successful run** vs **failed run** side by side
- **Slow span identification** — `get_weather` has an artificial 2.5 s delay to simulate a slow external API

---

## Prerequisites

**Gemini API key** — set `GEMINI_API_KEY`.

**Langfuse** — pick one:

| Option | Steps |
|---|---|
| **Cloud (recommended)** | Sign up at [cloud.langfuse.com](https://cloud.langfuse.com), create a project, copy the public and secret keys. |
| **Self-hosted (Docker)** | `docker run -p 3000:3000 langfuse/langfuse` then use `http://localhost:3000` as the host. |

---

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Environment variables

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."

# Only needed for self-hosted Langfuse; defaults to https://cloud.langfuse.com
export LANGFUSE_HOST="http://localhost:3000"
```

---

## Run

```bash
python agent.py
```

The script prints:
1. Live LLM input/output panels for each step of both runs
2. A per-span trace table per run (with the slow span flagged)
3. A side-by-side comparison of both runs
4. Direct URLs to both traces in the Langfuse UI

Open those URLs in your browser to explore the full waterfall trace.
