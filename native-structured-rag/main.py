"""
Naive RAG vs Structured RAG — comparison prototype.

Version A (Naive):    fixed-size character chunks → embed → top-3 cosine retrieval → answer
Version B (Structured): section-heading chunks → embed → top-5 retrieval → Gemini rerank → top-2 → answer
"""

import os
import re
import math
import time
import textwrap
from typing import List, Tuple

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ───────────────────────────────────────────────────────────────────

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

EMBED_MODEL = "gemini-embedding-2"
GEN_MODEL = "gemini-2.5-flash"
DOCUMENT_PATH = "document.md"

QUESTIONS = [
    "What is the p99.9 Target internal processing time for Write Operations?",
    "Does the Free Tier support the RESTORE API operation?",
    "Should I use the `PUT /v1/buckets/{bucket}/cors` endpoint in my new application?",
    "Is the `GET /v1/billing/usage` endpoint officially deprecated?",
    "Is the `DELETE /v1/objects/bulk` endpoint scheduled for removal in v3.0?",
]


# ── Chunking ─────────────────────────────────────────────────────────────────


def naive_chunks(text: str, size: int = 300, overlap: int = 10) -> List[str]:
    """Splits text into fixed-size character windows with overlap.

    Returns a list of string chunks. Overlap ensures context is preserved
    across boundaries.
    """
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def structured_chunks(text: str) -> List[str]:
    """Splits text at markdown headings, keeping the heading with its body.

    Uses a lookahead regex to find #, ##, or ### at the start of lines.
    Filters out very short fragments (under 50 chars).
    """
    # Lookahead regex splits without consuming the heading tokens
    parts = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if len(p.strip()) > 50]


# ── Embedding & Similarity ───────────────────────────────────────────────────


def embed(text: str) -> List[float]:
    """Generates a vector embedding for the given text using gemini-embedding-2.

    Truncates input to 8000 characters to stay within model limits.
    Returns the raw float vector.
    """
    result = client.models.embed_content(model=EMBED_MODEL, contents=text[:8000])
    return result.embeddings[0].values


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculates the cosine similarity between two float vectors.

    Adds a small epsilon to the denominator to prevent division by zero.
    """
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b + 1e-10)


# ── Retrieval ─────────────────────────────────────────────────────────────────


def retrieve(
    query_emb: List[float],
    chunks: List[str],
    chunk_embs: List[List[float]],
    k: int,
) -> List[Tuple[str, float]]:
    """Finds the k most similar chunks to a query vector.

    Calculates cosine similarity for all chunks and returns the top k
    candidates paired with their similarity scores.
    """
    scored = [
        (chunk, cosine_similarity(query_emb, emb))
        for chunk, emb in zip(chunks, chunk_embs)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ── Reranking (Structured RAG only) ──────────────────────────────────────────


def rerank_score(query: str, chunk: str) -> int:
    """Assigns a relevance score (0-10) to a chunk using the LLM.

    Asks the model to evaluate how well the passage answers the query.
    Returns 0 if the model output is not a valid integer.
    """
    prompt = (
        f"Query: {query}\n\n"
        f"Passage:\n{chunk[:1500]}\n\n"
        "Rate how relevant this passage is to answering the query. "
        "Respond with a single integer from 0 (irrelevant) to 10 (directly answers the query)."
    )
    resp = client.models.generate_content(model=GEN_MODEL, contents=prompt)
    try:
        return int(resp.text.strip())
    except ValueError:
        return 0


def rerank(
    query: str,
    candidates: List[Tuple[str, float]],
    top_k: int,
) -> List[Tuple[str, int]]:
    """Scores candidate chunks with an LLM and returns the top k.

    Performs point-wise reranking by calling rerank_score on each candidate.
    Returns chunks sorted by LLM relevance score.
    """
    scored = [(chunk, rerank_score(query, chunk)) for chunk, _ in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ── Display Helpers ───────────────────────────────────────────────────────────


def display_model_input(prompt: str, label_color: str = "cyan"):
    """Styles and prints the synthesized generation prompt in a grey panel."""
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent="        ")
    content = Text.assemble(("PROMPT: ", f"bold {label_color}"), (wrapped, label_color))

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
    """Styles and prints the final model response in a grey panel."""
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


# ── Answer Generation ─────────────────────────────────────────────────────────


def answer(query: str, context_chunks: List[str], label_color: str = "cyan") -> str:
    """Generates a concise answer based solely on the provided context.

    Joins multiple chunks into a single context block.
    Instructs the LLM to be concise (max 2 sentences).
    Displays the generated prompt and the model response visually.
    """
    context = "\n\n---\n\n".join(context_chunks)
    prompt = (
        "Answer the following question using only the provided context and nothing else. "
        "Be concise — one or two sentences maximum.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )

    # Optional: Display the prompt (can be noisy, but required by skill specs)
    # display_model_input(prompt, label_color)

    response = client.models.generate_content(
        model=GEN_MODEL, contents=prompt
    ).text.strip()
    return response


# ── Answer Quality Evaluation ─────────────────────────────────────────────────


def evaluate(query: str, answer_text: str, reference_doc: str) -> int:
    """Evaluates answer quality on a 1-5 scale against the source document.

    Uses the LLM as a judge to check for accuracy and completeness.
    Compares against the full reference document.
    """
    prompt = (
        f"Question: {query}\n\n"
        f"Answer to evaluate:\n{answer_text}\n\n"
        f"Reference document:\n{reference_doc}\n\n"
        "Rate the answer on accuracy and completeness from 1 (wrong or missing key facts) "
        "to 5 (fully accurate and complete). Respond with a single integer only."
    )
    resp = client.models.generate_content(model=GEN_MODEL, contents=prompt)
    try:
        return int(resp.text.strip())
    except ValueError:
        return 0


# ── Main ──────────────────────────────────────────────────────────────────────


def embed_all(chunks: List[str], label: str) -> List[List[float]]:
    """Embeds a list of chunks sequentially with a small delay.

    Prints progress to the console during the operation.
    Returns a list of embedding vectors.
    """
    embeddings = []
    for i, chunk in enumerate(chunks):
        console.print(
            f"  [dim][{label}][/dim] embedding chunk {i+1}/{len(chunks)} ...", end="\r"
        )
        embeddings.append(embed(chunk))
        time.sleep(0.05)
    console.print()
    return embeddings


def main():
    """Execution entry point for the RAG comparison prototype.

    Loads the document, prepares both naive and structured chunks,
    runs retrieval/answer/eval for each test question, and prints a
    comparison summary using rich formatting.
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold yellow]Naive RAG vs Structured RAG[/bold yellow]\n"
            "[dim]A performance comparison between fixed-chunking and heading-based retrieval.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Ensure the document exists before attempting to read it
    if not os.path.exists(DOCUMENT_PATH):
        console.print(f"[bold red]Error:[/bold red] File '{DOCUMENT_PATH}' not found.")
        raise SystemExit(1)

    with open(DOCUMENT_PATH) as f:
        doc = f.read()

    naive_c = naive_chunks(doc)
    struct_c = structured_chunks(doc)

    naive_avg = sum(len(c) for c in naive_c) // max(1, len(naive_c))
    struct_avg = sum(len(c) for c in struct_c) // max(1, len(struct_c))

    console.print(Rule("[bold]Document Stats[/bold]", style="white"))
    console.print(f"  Total chars          : [bold]{len(doc):,}[/bold]")
    console.print(
        f"  Naive chunks         : [cyan]{len(naive_c):>3}[/cyan]   (avg {naive_avg:>5} chars)"
    )
    console.print(
        f"  Structured chunks    : [magenta]{len(struct_c):>3}[/magenta]   (avg {struct_avg:>5} chars)"
    )
    console.print()

    console.print("[dim]Embedding all chunks...[/dim]")
    naive_embs = embed_all(naive_c, "naive")
    struct_embs = embed_all(struct_c, "structured")
    console.print()

    results = []

    for idx, question in enumerate(QUESTIONS):
        console.print(
            f"[bold cyan]-- Q{idx+1} ----------------------------------------------------[/bold cyan]"
        )
        console.print(f"  [bold]Query:[/bold] {question}")
        console.print()

        q_emb = embed(question)
        time.sleep(0.1)

        # ── Version A: Naive RAG ──────────────────────────────────────
        top_a = retrieve(q_emb, naive_c, naive_embs, k=3)
        ans_a = answer(question, [c for c, _ in top_a], "cyan")
        quality_a = evaluate(question, ans_a, doc)
        sim_a = [f"{s:.2f}" for _, s in top_a]

        console.print(
            f"  [cyan]Naive[/cyan]      (k=3) q:{quality_a}/5  sim: {', '.join(sim_a)}"
        )
        display_model_output(ans_a)

        # ── Version B: Structured RAG ─────────────────────────────────
        top_b_initial = retrieve(q_emb, struct_c, struct_embs, k=5)
        top_b = rerank(question, top_b_initial, top_k=2)
        ans_b = answer(question, [c for c, _ in top_b], "magenta")
        quality_b = evaluate(question, ans_b, doc)
        rel_b = [str(s) for _, s in top_b]

        console.print(
            f"  [magenta]Structured[/magenta] (k=2) q:{quality_b}/5  rel: {', '.join(rel_b)}"
        )
        display_model_output(ans_b)

        # ── Verdict ───────────────────────────────────────────────────
        if quality_a == quality_b:
            verdict = "[yellow]TIE[/yellow]"
        elif quality_a > quality_b:
            verdict = "[cyan]NAIVE WINS[/cyan]"
        else:
            verdict = "[magenta]STRUCTURED WINS[/magenta]"

        console.print(f"  [bold]Verdict:[/bold]   {verdict}")
        console.print()

        results.append((quality_a, quality_b, verdict))

    # ── Summary ───────────────────────────────────────────────────────────────
    naive_wins = sum(1 for _, _, v in results if "NAIVE WINS" in v)
    struct_wins = sum(1 for _, _, v in results if "STRUCTURED WINS" in v)
    ties = sum(1 for _, _, v in results if "TIE" in v)
    avg_naive = sum(a for a, _, _ in results) / len(results)
    avg_struct = sum(b for _, b, _ in results) / len(results)

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    summary_table = Table(show_lines=True)
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Naive RAG", justify="center", style="cyan")
    summary_table.add_column("Structured RAG", justify="center", style="magenta")

    summary_table.add_row("Wins", f"{naive_wins}", f"{struct_wins}")
    summary_table.add_row("Ties", f"{ties}", f"{ties}")
    summary_table.add_row(
        "Avg Quality", f"{avg_naive:.1f} / 5", f"{avg_struct:.1f} / 5"
    )

    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    main()
