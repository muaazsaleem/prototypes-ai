# Naive RAG vs Structured RAG

Compares two RAG pipelines on the same document and five questions to show that **chunking strategy and reranking are accuracy levers, not implementation details**.

## What it builds

| | Version A — Naive RAG | Version B — Structured RAG |
|---|---|---|
| Chunking | Fixed 600-char windows with 60-char overlap | Split at markdown section headings |
| Retrieval | Top-3 by cosine similarity | Top-5 by cosine similarity |
| Reranking | None | Gemini scores each candidate 0–10; top-2 kept |
| Context sent | 3 chunks | 2 chunks |

The document is a realistic 20-section product spec (`document.md`). Five questions are chosen so their answers sit inside named sections — which naive chunking can split mid-sentence or silently strip the heading from.

## Why structured chunking wins

A naive chunk that starts 300 characters into "Section 8.2 Deleted File Recovery Window" carries no heading — the embedding has no signal that this chunk is *about* deleted-file retention. The structured chunk always includes `### 8.2 Deleted File Recovery Window` as its first line, making the embedding far more semantically precise.

Reranking adds a second pass: instead of relying only on vector distance, the LLM directly scores each candidate chunk's relevance to the query. This catches cases where cosine similarity ranks a broadly-related chunk above the actually-correct one.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python rag.py
```

Runtime: ~2–3 minutes (embedding ~50 chunks + 5 × reranking + 5 × evaluation).

## Sample output

```
==============================================================
DOCUMENT STATS
==============================================================
  Total chars          : 19,284
  Naive chunks         :  32   (avg   602 chars each)
  Structured chunks    :  28   (avg   688 chars each)

==============================================================
Q1: What is the maximum file size allowed for a single file upload?
==============================================================
  [Naive]      chunks=3  cos-sim: 0.84, 0.76, 0.61    quality: 3/5
  [Structured] chunks=2  rerank:  10, 8                quality: 5/5
  Verdict : STRUCTURED WINS
...
==============================================================
OVERALL RESULTS
==============================================================
  Naive RAG wins       : 1/5
  Structured RAG wins  : 4/5
  Ties                 : 0/5
  Avg quality (Naive)  : 2.8 / 5
  Avg quality (Struct) : 4.6 / 5
==============================================================
```

## Key concept

Chunking determines what the retriever *can* find. Reranking determines what the model *sees*. Both decisions compound — a bad chunk can never be rescued by good reranking, and good chunks wasted on poor reranking still produce weak answers.
