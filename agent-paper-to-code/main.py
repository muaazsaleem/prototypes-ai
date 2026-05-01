import json
import os
import sys
import textwrap

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from agent import run_agent
from config import CHUNK_OVERLAP, CHUNK_SIZE, GEMINI_API_KEY, TOP_K_CHUNKS
from evaluator import evaluate as run_eval
from pdf_processor import chunk_text, extract_paper_metadata, load_pdf
from rag import RAGStore
from semantic_cache import SemanticCache

console = Console()


def _print_eval_table(results: dict) -> None:
    """Renders RAGAS evaluation scores as a color-coded Rich table.

    Scores are categorized by color: green (>= 0.7), yellow (>= 0.4), and red (< 0.4).
    The table includes faithfulness, context relevance, and answer relevance metrics,
    along with an overall score calculated by the evaluator.
    """
    table = Table(
        title="RAGAS-Inspired Evaluation",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Metric", style="bold")
    table.add_column("Score", justify="center")
    table.add_column("Reason")

    for key in ("faithfulness", "context_relevance", "answer_relevance"):
        score = results[key]["score"]
        # Apply semantic color based on score thresholds
        color = "green" if score >= 0.7 else ("yellow" if score >= 0.4 else "red")
        table.add_row(
            key.replace("_", " ").title(),
            f"[{color}]{score:.2f}[/{color}]",
            results[key]["reason"],
        )

    table.add_section()
    table.add_row("Overall", f"[bold]{results['overall']:.2f}[/bold]", "")
    console.print(table)
    console.print()


def main():
    """Executes the Paper-to-Code pipeline from PDF ingestion to code evaluation.

    The pipeline involves PDF parsing, metadata extraction, RAG index construction,
    semantic cache lookup, and an agentic loop for code generation. Results are
    validated using a RAGAS-inspired evaluation framework.
    """
    # Validate command line arguments and environment configuration
    if len(sys.argv) < 2:
        console.print("[bold red]Error:[/bold red] Missing PDF path.")
        console.print("[dim]Usage: python main.py <paper.pdf>[/dim]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {pdf_path}")
        sys.exit(1)

    if not GEMINI_API_KEY:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY is not set.")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Display application header
    console.print(
        Panel.fit(
            "[bold yellow]Paper-to-Code Agent[/bold yellow]\n"
            "[dim]Autonomous implementation of research algorithms via RAG & Agentic Loops[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    console.print(Rule("[bold]Phase 1: Ingestion & Metadata[/bold]", style="white"))
    console.print()

    console.print(
        "[bold cyan]-- Loading and chunking PDF --------------------------[/bold cyan]"
    )
    raw_text = load_pdf(pdf_path)
    chunks = chunk_text(raw_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    console.print(f"   {len(raw_text):,} chars  →  [bold]{len(chunks)}[/bold] chunks")

    console.print(
        "\n[bold cyan]-- Extracting paper metadata -------------------------[/bold cyan]"
    )
    metadata = extract_paper_metadata(raw_text, client)
    console.print(f"   Title  : [dim]{metadata.get('title')}[/dim]")
    console.print(f"   Method : [bold]{metadata.get('method')}[/bold]")
    console.print()

    console.print(Rule("[bold]Phase 2: RAG Indexing[/bold]", style="white"))
    console.print()

    console.print(
        "[bold magenta]-- Building ChromaDB index --------------------------[/bold magenta]"
    )
    rag = RAGStore(client)
    rag.clear()  # reset vector store for fresh run
    rag.index_chunks(chunks)
    console.print(
        f"   Indexed [bold]{rag.count()}[/bold] chunks with Gemini embeddings"
    )
    console.print()

    # Formulate the implementation request
    query = (
        f"Implement the {metadata.get('method', 'core algorithm')} "
        f"from '{metadata.get('title', 'this paper')}' in Python"
    )

    console.print(Rule("[bold]Phase 3: Logic Generation[/bold]", style="white"))
    console.print()

    console.print(
        "[bold blue]-- Checking semantic cache --------------------------[/bold blue]"
    )
    cache = SemanticCache()
    query_embedding = rag.embed(query)
    cached = cache.get(query_embedding)

    if cached:
        cached_query, generated_code = cached
        console.print("   [bold green]Cache HIT[/bold green] — reusing previous result")
        console.print(f'   Matched: [dim]"{cached_query[:80]}..."[/dim]')
        console.print()
    else:
        console.print("   [yellow]Cache MISS[/yellow] — initiating agent reasoning")

        # LLM Input Styling for the Query
        input_elements = []
        wrapped_query = textwrap.fill(query, width=82, subsequent_indent="      ")
        input_elements.append(
            Text.assemble(("USER: ", "bold blue"), (wrapped_query, "blue"))
        )
        console.print(
            Panel(
                Group(*input_elements),
                title="[bold bright_black]Model Input[/bold bright_black]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )
        console.print()

        console.print(
            "[bold yellow]-- Retrieving relevant context ----------------------[/bold yellow]"
        )
        relevant_chunks = rag.retrieve(query, top_k=TOP_K_CHUNKS)
        console.print(f"   Found [bold]{len(relevant_chunks)}[/bold] relevant chunks")

        console.print(
            "\n[bold yellow]-- Running agent loop ------------------------------[/bold yellow]"
        )
        # Agent uses parallel tool execution to build the implementation
        generated_code, tool_log = run_agent(
            client, relevant_chunks, metadata, verbose=True
        )

        if tool_log:
            console.print(f"   Tools used: [bold]{len(tool_log)}[/bold]")
            for entry in tool_log:
                console.print(f"   → {entry['tool']}({list(entry['args'].keys())})")

        cache.set(query_embedding, query, generated_code)
        console.print("\n   [dim]Result stored in semantic cache.[/dim]")
        console.print()

    # LLM Output Styling for the Generated Code
    wrapped_response = "Generated Python implementation based on paper analysis."
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

    console.print("[bold]Generated Implementation:[/bold]")
    console.print(
        Panel(
            Syntax(generated_code, "python", theme="monokai", line_numbers=True),
            title="[green]implementation.py[/green]",
        )
    )
    console.print()

    # Persist the implementation to disk
    output_path = "generated_implementation.py"
    with open(output_path, "w") as f:
        f.write(generated_code)
    console.print(f"   Saved → [cyan]{output_path}[/cyan]\n")

    console.print(
        Rule("[bold yellow]Phase 4: Evaluation[/bold yellow]", style="yellow")
    )
    console.print()

    console.print(
        "[bold cyan]-- Running RAGAS assessment -------------------------[/bold cyan]"
    )
    eval_chunks = rag.retrieve(query, top_k=3)
    results = run_eval(client, query, eval_chunks, generated_code)
    _print_eval_table(results)

    # Save evaluation results for future analysis
    eval_path = "eval_results.json"
    with open(eval_path, "w") as f:
        json.dump(results, f, indent=2)
    console.print(f"   Saved → [cyan]{eval_path}[/cyan]\n")


if __name__ == "__main__":
    main()
