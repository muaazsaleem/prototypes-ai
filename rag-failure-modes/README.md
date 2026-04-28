# Prototype 8: RAG Failure Mode Showcase

Demonstrates three distinct, diagnosable RAG failure modes on the same 15-document corpus. Each failure is caught by a different RAGAS metric.

## The Three Failures

| # | Mode | What goes wrong | Diagnostic metric |
|---|------|-----------------|-------------------|
| 1 | **Retrieval Miss** | Answer exists in the corpus but TF-IDF never retrieves it — query says "founders/created", corpus says "established/initiated" | `context_recall` → low |
| 2 | **Lost in the Middle** | Answer chunk is retrieved but placed at position 8 of 15; model attends to edges and ignores the middle | `context_precision` → low |
| 3 | **Faithfulness Failure** | Only FY2022 revenue data exists; aggressive prompt pushes model to state a confident FY2023 figure the context never supports | `faithfulness` → low |

## RAGAS Metrics (implemented directly with Gemini)

| Metric | What it measures |
|--------|-----------------|
| `faithfulness` | Fraction of claims in the answer that are explicitly supported by the retrieved context |
| `context_recall` | Fraction of ground-truth statements attributable to the retrieved context |
| `context_precision` | Average precision@k — rewards useful chunks ranked near the top |
| `answer_relevancy` | Cosine similarity between the original question and N reverse-generated questions from the answer |

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=<your-key>
```

## Run

```bash
python prototype8.py
```

Takes ~2–3 minutes (each failure mode makes ~15–20 LLM calls for metric computation).
