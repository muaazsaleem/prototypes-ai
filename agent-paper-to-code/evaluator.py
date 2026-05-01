"""
RAGAS-inspired evaluation for the Paper-to-Code agent.

RAGAS (Retrieval-Augmented Generation Assessment) defines three core metrics:

  Faithfulness       — is the answer grounded in the retrieved context?
  Context Relevance  — are the retrieved chunks actually relevant to the query?
  Answer Relevance   — does the answer address the question that was asked?

We implement each metric by prompting Gemini to act as an LLM judge and return
a score in [0, 1] plus a one-sentence rationale. This is the same "LLM-as-judge"
pattern used internally by the RAGAS library.
"""

import json
from typing import Dict, List, Tuple

from google import genai

from config import GEMINI_MODEL


def _llm_score(client: genai.Client, prompt: str) -> Tuple[float, str]:
    """Call Gemini and parse a {"score": float, "reason": str} JSON response.

    Returns (0.0, "parse error") if the model wraps its output in unexpected text
    or returns malformed JSON — keeps the evaluation pipeline from crashing.
    """
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    try:
        raw = response.text.strip()
        # Strip markdown code fences — Gemini sometimes wraps JSON in them
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        return float(parsed.get("score", 0.0)), str(parsed.get("reason", ""))
    except Exception:
        return 0.0, "parse error"


def faithfulness(
    client: genai.Client, context_chunks: List[str], generated_code: str
) -> Tuple[float, str]:
    """
    Faithfulness: every claim in the generated code should be traceable to
    the retrieved paper context — the model must not invent methods or parameters.
    Score 1.0 → fully grounded | 0.0 → entirely hallucinated.
    """
    ctx = "\n\n".join(context_chunks[:3])[:2500]
    code_snippet = generated_code[:2000]

    prompt = f"""You are evaluating whether generated Python code faithfully implements the algorithm described in the paper excerpts below.

Paper excerpts:
{ctx}

Generated code:
{code_snippet}

Scoring rubric:
1.0 — Every major step in the code maps directly to a claim in the paper.
0.5 — Some steps match the paper; others are invented or inaccurate.
0.0 — The code does not reflect the paper's method at all.

Respond ONLY with valid JSON: {{"score": <float 0-1>, "reason": "<one sentence>"}}"""

    return _llm_score(client, prompt)


def context_relevance(
    client: genai.Client, query: str, context_chunks: List[str]
) -> Tuple[float, str]:
    """
    Context Relevance: how much of the retrieved content is actually useful
    for answering the query. High noise → low score.
    Score 1.0 → all chunks are on-topic | 0.0 → completely off-topic.
    """
    ctx = "\n\n".join(context_chunks[:3])[:2500]

    prompt = f"""Evaluate how relevant these retrieved paper excerpts are to the implementation query below.

Query: {query}

Retrieved excerpts:
{ctx}

Scoring rubric:
1.0 — Excerpts contain exactly the information needed to implement the method.
0.5 — Some excerpts are relevant; others are noise.
0.0 — Excerpts are unrelated to the query.

Respond ONLY with valid JSON: {{"score": <float 0-1>, "reason": "<one sentence>"}}"""

    return _llm_score(client, prompt)


def answer_relevance(
    client: genai.Client, query: str, generated_code: str
) -> Tuple[float, str]:
    """
    Answer Relevance: does the generated code actually address the request?
    A complete implementation scores higher than a skeleton or off-topic snippet.
    Score 1.0 → fully answers the request | 0.0 → irrelevant.
    """
    code_snippet = generated_code[:2000]

    prompt = f"""Evaluate whether the generated Python code is a relevant and complete response to the implementation request.

Request: {query}

Generated code:
{code_snippet}

Scoring rubric:
1.0 — Code implements exactly what was requested and is runnable.
0.5 — Code is partially relevant or incomplete.
0.0 — Code does not address the request.

Respond ONLY with valid JSON: {{"score": <float 0-1>, "reason": "<one sentence>"}}"""

    return _llm_score(client, prompt)


def evaluate(
    client: genai.Client,
    query: str,
    context_chunks: List[str],
    generated_code: str,
) -> Dict:
    """Run all three RAGAS-inspired metrics and return a summary dict.

    Each metric is an independent LLM call; results are combined into a flat
    dict with per-metric score+reason entries and a simple arithmetic mean as
    the overall score. The overall score is rounded to 3 decimal places.
    """
    f_score, f_reason = faithfulness(client, context_chunks, generated_code)
    c_score, c_reason = context_relevance(client, query, context_chunks)
    a_score, a_reason = answer_relevance(client, query, generated_code)
    overall = round((f_score + c_score + a_score) / 3, 3)  # simple mean across metrics

    return {
        "faithfulness": {"score": f_score, "reason": f_reason},
        "context_relevance": {"score": c_score, "reason": c_reason},
        "answer_relevance": {"score": a_score, "reason": a_reason},
        "overall": overall,
    }
