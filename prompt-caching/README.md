# Prompt Caching — Hit Rate Economics

Demonstrates the cost and latency impact of prompt caching using **Gemini 2.5 Flash**'s context caching API across three phases.

---

## What this prototype shows

| Phase | What happens |
|-------|-------------|
| **Phase 1** | 20 API calls, no caching. Full system prompt (~2500 tokens) is tokenised and billed on every call. |
| **Phase 2** | System prompt is written to a cache once. 20 calls reference the cache — each pays only the cheap cache-read rate. |
| **Phase 3** | One sentence is changed in the system prompt. The old cache is invalid; a new cache write is required — showing the fragility. |

The prototype then prints:
- Token counts (prompt / cached / output) per phase
- USD cost per phase (input + output + cache-write)
- Cache hit rate and cost reduction percentage
- Average, p50, and p95 latency per phase
- A side-by-side comparison table with net savings

---

## The core concept

Prompt caching is extremely high-leverage when:
- The system prompt is large (hundreds to thousands of tokens)
- The same prompt is reused across many calls
- The prompt is **stable** — any edit invalidates the cache

Gemini 2.5 Flash charges **~75% less** for cached input tokens vs. standard input tokens.  
For a 2500-token system prompt used in 20 calls:

- **Without cache**: 20 × 2500 = **50,000 input tokens** billed at full price
- **With cache**: 1 × 2500 cache-write + 20 × 2500 cache-read at ~4× cheaper rate

The savings grow linearly with call count and prompt size.

**The fragility**: changing even one character in the cached content forces a full rewrite. This means cache design must be considered when writing prompts — stable, reusable content belongs at the top; dynamic, per-request content stays outside the cache.

---

## Pricing reference (Gemini 2.5 Flash)

| Token type | Price per 1M tokens |
|-----------|-------------------|
| Standard input | $0.15 |
| Cached input (read) | $0.037 |
| Output | $0.60 |
| Cache write (one-time) | $1.00 |

*Source: [Google AI Gemini pricing](https://ai.google.dev/gemini-api/docs/models)*

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Gemini API key
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

The run takes approximately **3–6 minutes** (40 live API calls + 4 cache operations).

---

## Expected output structure

```
┌─ Prompt Caching — Hit Rate Economics ─────────────────────────────┐
│  Cost and latency impact of prompt caching with Gemini 2.5 Flash. │
│  20 calls × 3 phases: no cache / with cache / invalidation        │
└───────────────────────────────────────────────────────────────────┘

── Phase 1 — Without Caching ────────────────────────────────────────
  Run #01: o  2.31s  2548 in / 87 out   Run #02: o  ...
  ...

┌─ Phase 1 — No Caching ─────────────────────────────────────────────┐
│  Total Prompt Tokens      50,960                                    │
│  Cache Hit Rate           0.0%                                      │
│  Total Cost               $0.007644                                 │
│  Avg Latency              2.41s                                      │
└─────────────────────────────────────────────────────────────────────┘

── Phase 2 — With Caching ───────────────────────────────────────────
  Run #01: o HIT  1.12s  2548/2548 cached   ...

┌─ Phase 2 — With Caching ───────────────────────────────────────────┐
│  Total Prompt Tokens      50,960                                    │
│  — Cached                 50,960                                    │
│  Cache Hit Rate           100.0%                                    │
│  Total Cost               $0.002190                                 │
│  Avg Latency              1.08s                                      │
└─────────────────────────────────────────────────────────────────────┘

══ Overall Summary ══════════════════════════════════════════════════
  Cost reduction:   71.4%  (saving $0.005454 across 20 calls)
  Latency speedup:  55.2%  (2.41s → 1.08s avg per call)

── Phase 3 — Cache Invalidation ─────────────────────────────────────
  - You are a Principal Database Architect with 25 years ...
  + You are a Senior Database Architect with 20 years ...
  New cache write required: Yes — old cache is invalid
```

*(Exact numbers will vary based on model responses and API latency.)*
