# Evals-Driven Development Cycle

**Concept demonstrated:** Evals are the product spec. Build to the eval, not to vibes.

---

## What this prototype shows

Most teams build an AI feature, poke at it manually, say "looks good", and ship.
This prototype demonstrates why that is the wrong way to work and what to do instead.

The correct order is:
1. **Write the eval first** — define the test cases, expected outputs, and scorer before writing any prompt
2. **Run baseline** — measure where you start
3. **Improve** — change the prompt or add retrieval; re-run the eval to see if it actually helps
4. **Watch for regressions** — an aggregate score that goes up can still hide individual cases getting worse

### Domain

The system answers questions about **StreamProcessor** — a fictional Python streaming library
that Gemini 2.5 Flash has never seen. This makes it easy to show failure (the model guesses)
and recovery (RAG injects real facts).

### Three iterations

| Iteration | Strategy | What it demonstrates |
|---|---|---|
| Baseline (Zero-Shot) | Raw question, no guidance | Score is low; product-specific questions fail |
| Improved Prompt | System prompt with key facts baked in | Score climbs; shows prompt engineering has real lift |
| RAG-Enhanced | Retrieve top-2 docs per question, inject as context | Score climbs again; but one case *regresses* |

### The regression

Case 1 asks: *"What does raising `NotImplementedError` in a Python base class conventionally signal?"*

- **Baseline / Improved:** The model draws on its Python knowledge and answers correctly (abstract base class, subclasses must override).
- **RAG:** The word-overlap retriever ranks the *Error Handling* doc first for this question. That doc describes how **StreamProcessor** raises `NotImplementedError` when a connector plugin is missing. The model follows the documentation and gives a StreamProcessor-specific answer — missing the general Python convention.

The aggregate score improves from Improved → RAG (+5 or +6 cases), so the regression on Case 1 is completely invisible in the headline number. This is the point: **never ship without per-case eval breakdowns.**

---

## Eval design

- **15 test cases** — 3 general Python questions + 12 StreamProcessor-specific questions
- **Scorer** — keyword match: the fraction of required keywords that appear in the response; pass threshold is 60%
- **Retriever** — simple word-overlap (no embeddings); ranks knowledge base docs by token intersection with the question

---

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set your Gemini API key:

```bash
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

The script makes 45 API calls (15 cases × 3 iterations) and takes roughly 2–4 minutes.
Output shows a live dot per case, then per-iteration tables, a score comparison, and a
detailed regression analysis with the full LLM exchange for the regression case in each iteration.
