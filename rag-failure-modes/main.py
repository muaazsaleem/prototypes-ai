#!/usr/bin/env python3
"""
Prototype 8: RAG Failure Mode Showcase

Three failure modes (Retrieval Miss, Lost in the Middle, Faithfulness Failure)
demonstrated on a 15-document corpus with RAGAS-style metrics.
"""

import os
import re
import json
import math
import time
import textwrap
from collections import Counter
from typing import List, Tuple

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEN_MODEL = "gemini-2.5-flash"
EMB_MODEL = "gemini-embedding-2"

# ── Corpus ────────────────────────────────────────────────────────────────────

CORPUS = [
    "NovaTech was established in 2018 and initiated by two veterans of the robotics and aerospace sectors.",
    "The company builds autonomous drone software for agricultural monitoring and precision farming.",
    "NovaTech completed an $8 million Series A round led by Sequoia Capital in March 2020.",
    "Dr. Priya Kapoor and James Liu are the principal architects behind NovaTech's technology platform.",
    "DroneOS, NovaTech's flagship product, is deployed on over 300 farms across the United States.",
    "In 2021, NovaTech expanded into Latin America through a partnership with AgriMex in Mexico City.",
    "NovaTech's annual recurring revenue was $6.5 million at the end of fiscal year 2021.",
    "James Liu brought six years of avionics expertise from SpaceX before co-founding NovaTech.",
    "NovaTech employs 87 engineers and 23 business development professionals across all offices.",
    "NovaTech's Austin headquarters occupies 12,000 square feet in the Domain district.",
    "NovaTech won the 2022 AgriTech Innovation Award from the American Farm Bureau.",
    "DroneOS processes field imagery on-device using edge AI, with no cloud connectivity needed.",
    "NovaTech plans to launch a seed-spreading drone attachment in Q3 2024.",
    "NovaTech's revenue reached $9.2 million in fiscal year 2022, a 41% year-over-year increase.",
    "NovaTech has filed 14 patents on autonomous drone navigation and obstacle avoidance since 2019.",
    "The founders of the Global Robotics Initiative created a charter in 2012 for ethical AI.",
    "A new startup was created by the founders of several Silicon Valley firms to study soil health.",
    "The founders of AgriMex created a regional distribution hub in 2019.",
    "Historical records show the town of Nova was created by founders in the early 19th century.",
    "Many tech companies are created by founders who previously worked at large conglomerates.",
]

# Adding 30+ noise documents for Lost-in-the-Middle
NOISE = [
    f"Random technical detail #{i}: The sensor calibration offset is set to {i*0.123:.3f} units."
    for i in range(40)
]
EXTENDED_CORPUS = CORPUS + NOISE

# ── TF-IDF Retrieval ──────────────────────────────────────────────────────────


def _tok(text: str) -> List[str]:
    """Tokenizes text into a list of lowercase alphanumeric words."""
    return re.findall(r"\b[a-z]+\b", text.lower())


def build_index(corpus: List[str]) -> Tuple[List[dict], dict]:
    """Builds a TF-IDF index for the given corpus.

    Returns a list of document vectors (dicts) and the global IDF dictionary.
    """
    tokenized = [_tok(d) for d in corpus]
    N = len(corpus)
    # count documents containing each word
    df = Counter(w for tokens in tokenized for w in set(tokens))
    # calculate inverse document frequency with smoothing
    idf = {w: math.log((N + 1) / (df[w] + 1)) for w in df}

    def vec(tokens: List[str]) -> dict:
        """Converts a list of tokens into a TF-IDF vector."""
        tf = Counter(tokens)
        n = len(tokens) or 1
        return {w: (c / n) * idf[w] for w, c in tf.items()}

    return [vec(t) for t in tokenized], idf


def _cos(a: dict, b: dict) -> float:
    """Calculates cosine similarity between two sparse TF-IDF vectors."""
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    # normalize by magnitudes to get cosine similarity
    return dot / (
        math.sqrt(sum(v**2 for v in a.values()))
        * math.sqrt(sum(v**2 for v in b.values()))
        + 1e-10
    )


def tfidf_retrieve(
    query: str, vectors: List[dict], idf: dict, k: int = 3
) -> List[Tuple[int, str, float]]:
    """Retrieves the top-k most relevant documents from the index using TF-IDF."""
    q_tokens = _tok(query)
    total = len(q_tokens) or 1
    tf = Counter(q_tokens)
    # build query vector using pre-computed global IDF
    q_vec = {w: (c / total) * idf.get(w, 0) for w, c in tf.items() if w in idf}
    ranked = sorted(range(len(vectors)), key=lambda i: -_cos(q_vec, vectors[i]))
    return [(i, CORPUS[i], _cos(q_vec, vectors[i])) for i in ranked[:k]]


# ── Embeddings ───────────────────────────────────────────────────────────────


def embed(text: str) -> List[float]:
    """Generates a dense vector embedding for the given text using Gemini."""
    r = client.models.embed_content(model=EMB_MODEL, contents=text)
    return r.embeddings[0].values


def cosine_emb(a: List[float], b: List[float]) -> float:
    """Calculates cosine similarity between two dense embedding vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x**2 for x in a))
    nb = math.sqrt(sum(x**2 for x in b))
    return dot / (na * nb + 1e-10)


# ── LLM Generation and Display ────────────────────────────────────────────────


def display_model_input(prompt: str):
    """Styles and prints the prompt inside a grey panel."""
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent="      ")
    content = Text.assemble(("USER: ", "bold blue"), (wrapped, "blue"))

    console.print(
        Panel(
            Group(content),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_model_output(response_text: str):
    """Styles and prints the model response in a grey panel."""
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
    )

    console.print(
        Panel(
            response_content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def generate(question: str, contexts: List[str], aggressive: bool = False) -> str:
    """Generates an answer to the question based on the provided context chunks.

    If aggressive is True, the model is pushed to provide specific numbers even
    if not clearly in context. Otherwise, it follows strict context grounding.
    """
    ctx = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    if aggressive:
        prompt = (
            "CRITICAL: You MUST provide a specific numerical dollar amount for the FY2023 revenue. "
            "If the exact figure is not in the context, use the 2022 revenue and growth rate to "
            "calculate/extrapolate the 2023 figure. Do NOT say you don't know. "
            "Format: '$X.X million'.\n\n"
            f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:"
        )
    else:
        prompt = (
            "Answer using ONLY the provided context. "
            "If the context does not contain the answer, say exactly: "
            "'The context does not contain this information.'\n\n"
            f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:"
        )

    display_model_input(prompt)
    answer = client.models.generate_content(
        model=GEN_MODEL, contents=prompt
    ).text.strip()
    display_model_output(answer)
    return answer


# ── RAGAS-style Metrics ───────────────────────────────────────────────────────


def _llm_json(prompt: str) -> dict:
    """Helper to get a structured JSON response from the LLM."""
    resp = client.models.generate_content(
        model=GEN_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(resp.text)


def metric_faithfulness(answer: str, contexts: List[str]) -> float:
    """Calculates faithfulness: the fraction of claims in the answer supported by context."""
    ctx = "\n".join(contexts)
    data = _llm_json(
        f'Context:\n{ctx}\n\nAnswer: "{answer}"\n\n'
        "List every factual claim in the answer. For each, say whether it is "
        "explicitly supported by the context above.\n"
        'Return JSON: {"claims": ["..."], "supported": [true/false, ...]}'
    )
    supported = data.get("supported", [])
    return (sum(supported) / len(supported)) if supported else 1.0


def metric_context_recall(
    question: str, ground_truth: str, contexts: List[str]
) -> float:
    """Calculates context recall: fraction of ground-truth statements found in context."""
    ctx = "\n".join(contexts)
    data = _llm_json(
        f'Context:\n{ctx}\n\nGround truth: "{ground_truth}"\n\n'
        "Break the ground truth into individual statements. "
        "For each, say whether it can be found in or directly inferred from the context.\n"
        'Return JSON: {"statements": ["..."], "found_in_context": [true/false, ...]}'
    )
    found = data.get("found_in_context", [])
    return (sum(found) / len(found)) if found else 0.0


def metric_context_precision(
    question: str, ground_truth: str, contexts: List[str]
) -> float:
    """Calculates context precision using Average Precision @ k."""
    useful = []
    for chunk in contexts:
        data = _llm_json(
            f'Question: {question}\nGround truth: {ground_truth}\nChunk: "{chunk}"\n\n'
            "Is this chunk useful for answering the question?\n"
            'Return JSON: {"useful": true/false}'
        )
        useful.append(bool(data.get("useful", False)))

    if not any(useful):
        return 0.0
    running, total = 0, 0.0
    for i, u in enumerate(useful):
        if u:
            running += 1
            # add precision at current rank to the running total
            total += running / (i + 1)
    return total / sum(useful)


def metric_answer_relevancy(question: str, answer: str, n: int = 3) -> float:
    """Calculates answer relevancy by reverse-generating questions from the answer."""
    data = _llm_json(
        f'Answer: "{answer}"\n\n'
        f"Generate {n} different questions that this answer would naturally respond to.\n"
        f'Return JSON: {{"questions": ["...", ...]}}'
    )
    questions = data.get("questions", [])
    if not questions:
        return 0.0
    q_emb = embed(question)
    # score original question against generated ones via cosine similarity
    scores = [cosine_emb(q_emb, embed(q)) for q in questions]
    return sum(scores) / len(scores)


def run_metrics(
    question: str, answer: str, contexts: List[str], ground_truth: str
) -> dict:
    """Executes all four RAGAS-style metrics and returns a summary dictionary."""
    return {
        "faithfulness": metric_faithfulness(answer, contexts),
        "context_recall": metric_context_recall(question, ground_truth, contexts),
        "context_precision": metric_context_precision(question, ground_truth, contexts),
        "answer_relevancy": metric_answer_relevancy(question, answer),
    }


# ── Display Helpers ───────────────────────────────────────────────────────────


def accuracy_bar(value: float, width: int = 28) -> Text:
    """Renders a visual bar for a metric score."""
    filled = round(value * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if value >= 0.8 else "yellow" if value >= 0.5 else "red"
    return Text(f"{bar}  {value:.3f}", style=color)


def print_metrics_table(scores: dict):
    """Prints a Rich table showing metric scores and visual bars."""
    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Metric", width=20)
    table.add_column("Score", justify="right")
    table.add_column("Distribution")

    for k, v in scores.items():
        table.add_row(k.replace("_", " ").title(), f"{v:.3f}", accuracy_bar(v))

    console.print(table)
    console.print()


# ── Failure Mode 1: Retrieval Miss ────────────────────────────────────────────


def failure_1_retrieval_miss(vectors: List[dict], idf: dict) -> dict:
    """Demonstrates failure when the retrieval step misses the correct documents."""
    console.print(Rule("[bold]Failure Mode 1: Retrieval Miss[/bold]", style="white"))
    question = "Who are the founders of NovaTech and when was the company created?"
    ground_truth = "NovaTech was established in 2018 by Dr. Priya Kapoor and James Liu."

    console.print(f"[bold]Q:[/bold] {question}")
    console.print(f"[bold]GT:[/bold] {ground_truth}")
    console.print(
        "[dim]Mismatched vocabulary: 'founders/created' (query) vs 'established/initiated/architects' (docs).[/dim]"
    )

    retrieved = tfidf_retrieve(question, vectors, idf, k=3)
    console.print(
        "\n[bold cyan]-- Top-3 Retrieved ------------------------------[/bold cyan]"
    )
    for rank, (idx, doc, score) in enumerate(retrieved, 1):
        marker = " [bold green]← ANSWER[/bold green]" if idx in (0, 3) else ""
        console.print(
            f"  [{rank}] doc[{idx:2d}] score={score:.4f}  [dim]{doc[:60]}...[/dim]{marker}"
        )
    console.print()

    contexts = [doc for _, doc, _ in retrieved]
    answer = generate(question, contexts)

    console.print("[dim]Computing metrics...[/dim]")
    scores = run_metrics(question, answer, contexts, ground_truth)
    print_metrics_table(scores)

    verdict = (
        "[bold red]RETRIEVAL_MISS[/bold red]"
        if scores["context_recall"] < 0.5
        else "[bold green]PASS[/bold green]"
    )
    console.print(f"[bold]Verdict (derived):[/bold] {verdict}\n")
    return scores


# ── Failure Mode 2: Lost in the Middle ───────────────────────────────────────


def failure_2_lost_in_middle() -> dict:
    """Demonstrates failure when the answer is buried in a long, noisy context."""
    console.print(
        Rule("[bold]Failure Mode 2: Lost in the Middle[/bold]", style="white")
    )
    question = "How many square feet is NovaTech's Austin headquarters?"
    ground_truth = "NovaTech's Austin headquarters occupies 12,000 square feet."

    # Create a long context with the answer buried in the middle
    noise_docs = [
        f"Technical Specification {i}: The voltage regulator maintains a steady {3.3 + i*0.01:.2f}V "
        f"output with a tolerance of {0.05 + i*0.001:.3f}% across all operating temperatures."
        for i in range(50)
    ]
    target = CORPUS[9]  # The headquarters info

    # Place target at position 25 (middle)
    contexts = noise_docs[:25] + [target] + noise_docs[25:]
    ans_position = 26

    console.print(f"[bold]Q:[/bold] {question}")
    console.print(f"[bold]GT:[/bold] {ground_truth}")
    console.print(
        f"[dim]Context length: {len(contexts)} chunks. Answer at position {ans_position}/{len(contexts)}.[/dim]\n"
    )

    answer = generate(question, contexts)

    console.print("[dim]Computing metrics...[/dim]")
    scores = run_metrics(question, answer, contexts, ground_truth)
    print_metrics_table(scores)

    verdict = (
        "[bold yellow]LOST_IN_MIDDLE[/bold yellow]"
        if scores["context_precision"] < 0.5
        else "[bold green]PASS[/bold green]"
    )
    console.print(f"[bold]Verdict (derived):[/bold] {verdict}\n")
    return scores


# ── Failure Mode 3: Faithfulness Failure ─────────────────────────────────────


def failure_3_faithfulness(vectors: List[dict], idf: dict) -> dict:
    """Demonstrates failure when the LLM hallucinates or ignores context constraints."""
    console.print(
        Rule("[bold]Failure Mode 3: Faithfulness Failure[/bold]", style="white")
    )
    question = "What was NovaTech's total revenue in fiscal year 2023?"
    ground_truth = (
        "NovaTech's FY2023 revenue is not documented in the available sources."
    )

    console.print(f"[bold]Q:[/bold] {question}")
    console.print(f"[bold]GT:[/bold] {ground_truth}")
    console.print(
        "[dim]Only FY2022 data exists ($9.2M). Aggressive prompt pushes model to commit to a figure.[/dim]\n"
    )

    retrieved = tfidf_retrieve(question, vectors, idf, k=3)
    contexts = [doc for _, doc, _ in retrieved]
    answer = generate(question, contexts, aggressive=True)

    console.print("[dim]Computing metrics...[/dim]")
    scores = run_metrics(question, answer, contexts, ground_truth)
    print_metrics_table(scores)

    verdict = (
        "[bold red]FAITHFULNESS_FAILURE[/bold red]"
        if scores["faithfulness"] < 0.8
        else "[bold green]PASS[/bold green]"
    )
    console.print(f"[bold]Verdict (derived):[/bold] {verdict}\n")
    return scores


# ── Summary ───────────────────────────────────────────────────────────────────


def show_summary(r1: dict, r2: dict, r3: dict):
    """Displays a side-by-side comparison of metrics across all three failure modes."""
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(show_lines=True, title="RAGAS Metrics Comparison")
    table.add_column("Metric", style="bold")
    table.add_column("Retrieval Miss", justify="center")
    table.add_column("Lost-in-Middle", justify="center")
    table.add_column("Faith. Failure", justify="center")

    keys = ["faithfulness", "context_recall", "context_precision", "answer_relevancy"]
    for k in keys:
        row_key = k.replace("_", " ").title()

        def highlight(val: float, condition: bool) -> str:
            """Formats the metric score, highlighting it in red if the condition is met."""
            s = f"{val:.3f}"
            return f"[bold red]{s}[/bold red]" if condition else s

        table.add_row(
            row_key,
            highlight(r1[k], k == "context_recall"),
            highlight(r2[k], k == "context_precision"),
            highlight(r3[k], k == "faithfulness"),
        )

    console.print(table)
    console.print(
        "\n[dim][bold red]Red text[/bold red] indicates the metric that primary diagnoses each failure mode.[/dim]\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    """Main entry point: sets up index and runs all failure mode demonstrations."""
    console.print(
        Panel.fit(
            "[bold yellow]RAG Failure Mode Showcase[/bold yellow]\n"
            "[dim]Demonstrating common pitfalls in Retrieval-Augmented Generation.[/dim]\n"
            "[dim]20 docs + 50 noise chunks | 3 failure modes | Gemini 2.0 Flash[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    console.print("[dim]Building TF-IDF index over corpus...[/dim]")
    vectors, idf = build_index(CORPUS)
    console.print()

    r1 = failure_1_retrieval_miss(vectors, idf)
    r2 = failure_2_lost_in_middle()
    r3 = failure_3_faithfulness(vectors, idf)

    show_summary(r1, r2, r3)


if __name__ == "__main__":
    main()
