# Natural Language Workflow Engine

Describe a multi-step data pipeline in plain English and the engine turns it into an executable DAG.

```
"Fetch top 10 HN posts and top 5 GitHub repos.
 Summarise both. Combine into a tech digest. Translate to Spanish."
```

The parser converts that sentence into a DAG of typed nodes. Independent nodes run in parallel via `asyncio.gather`. Each node streams its output back as it produces tokens. Every node execution is wrapped in an OpenTelemetry span so you can see per-node latency. All LLM nodes share a single cached Gemini system prompt (context caching) to avoid uploading the same large instruction set on every call.

## Architecture

```
main.py
 └─ parser.py        NL description → Workflow DAG  (Gemini structured output)
 └─ executor.py      Topological sort → waves → asyncio.gather per wave
     └─ nodes.py     Per-node runners: fetch / LLM (summarize/translate/…) / email
     └─ cache.py     Gemini context-cache manager  (shared system prompt)
     └─ tracing.py   OpenTelemetry setup  (console exporter)
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
# Default demo workflow (HN + GitHub → summarise → combine → translate to Spanish)
python main.py

# Custom workflow
python main.py "Fetch the BBC tech RSS feed, filter posts from the last 24 hours, summarise them, email to me@example.com"
```

## Key concepts shown

| Concept | Where |
|---|---|
| Structured output / constrained generation | `parser.py` — `response_schema=Workflow` |
| DAG + parallel execution | `executor.py` — `_build_execution_waves` + `asyncio.gather` |
| Streaming LLM output | `nodes.py` — `_run_llm` async generator |
| Gemini context caching | `cache.py` — `PromptCacheManager` |
| OpenTelemetry tracing | `tracing.py` + spans in `executor.py` |
