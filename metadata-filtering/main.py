import os
import json
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Initialize Rich Console
console = Console()

# Initialize the Gemini client
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# ---------------------------------------------------------------------------
# DATASET DEFINITIONS
# ---------------------------------------------------------------------------

# Dataset for Scenario 1: Hallucination & Retrieval Bottleneck
# Imagine a corpus of 100 documents. Vector search has a top_k limit of 2.
HALLUCINATION_CORPUS = [
    {
        "id": "DOC_001",
        "content": "Financial Summary: Total revenue reached $10M with 15% growth.",
        "metadata": {"year": 2024, "quarter": 1}
    },
    {
        "id": "DOC_002",
        "content": "Financial Summary: Total revenue reached $12M with 10% growth.",
        "metadata": {"year": 2025, "quarter": 1}
    },
    {
        "id": "DOC_003",
        "content": "Financial Summary: Total revenue reached $15M with 5% growth.",
        "metadata": {"year": 2026, "quarter": 1} # This is the target document
    },
]

# Dataset for Scenario 2: Security & Access Control
SECURITY_CORPUS = [
    {
        "id": "DOC_PUB_01",
        "content": "Acme Corp Office Holiday Policy: December 25th is a company-wide holiday.",
        "metadata": {"classification": "public", "allowed_roles": ["employee", "admin"]}
    },
    {
        "id": "DOC_SEC_02",
        "content": "CONFIDENTIAL: Project Phoenix planning to acquire competitor Delta Tech for $50M in Q3.",
        "metadata": {"classification": "confidential", "allowed_roles": ["admin"]}
    }
]

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def extract_filters(query: str):
    """Uses Gemini to extract structured filter criteria."""
    prompt = f"""
    Extract filtering criteria from the user query.
    Query: "{query}"
    Return a JSON object with 'year' (int) and 'quarter' (int).
    For 'quarter', convert strings like 'Q1' or 'first quarter' into the corresponding integer (1-4).
    If a filter is not mentioned, set it to null.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    try:
        data = json.loads(response.text)
        if isinstance(data, list):
            data = data[0] if data else {}
        if 'year' in data and data['year'] is not None:
            data['year'] = int(data['year'])
        if 'quarter' in data and data['quarter'] is not None:
            data['quarter'] = int(data['quarter'])
        return data
    except Exception as e:
        console.print(f"[bold red]Error parsing filters:[/bold red] {e}")
        return {}

def run_llm_query(prompt: str, label: str):
    """Executes a prompt on Gemini and prints the input/output panel."""
    console.print(Panel(Text(f"PROMPT:\n{prompt.strip()}", style="blue"), title=f"[bold bright_black]{label} Input[/bold bright_black]", border_style="bright_black"))
    
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    response_text = response.text.strip()
    
    console.print(Panel(Text(f"ASSISTANT: {response_text}", style="green italic"), title="[bold bright_black]Model Response[/bold bright_black]", border_style="bright_black"))
    return response_text

# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------

def demo_hallucination_and_retrieval():
    console.print(Rule("[bold yellow]SCENARIO 1: Hallucination & Retrieval Bottleneck[/bold yellow]", style="yellow"))
    console.print(
        "Demonstrates why putting metadata *only* in the prompt fails because of "
        "vector database search limits (top_k retrieval limits).\n"
    )
    
    query = "What was the revenue in Q1 2026?"
    console.print(f"[bold]User Query:[/bold] [cyan]{query}[/cyan]")
    console.print("[dim]We simulate a Vector DB search limit of TOP_K = 2 on a 3-doc dataset.[/dim]\n")

    # --- APPROACH A: Naive Search with Prompt-Level Metadata ---
    console.print("[bold red]Approach A: Naive RAG + Metadata in Prompt[/bold red]")
    console.print("[dim]Because the search is purely semantic and limited to top_k=2, the vector database[/dim]")
    console.print("[dim]returns the two oldest documents because they share high semantic similarity.[/dim]")
    console.print("[dim]The correct target document (Q1 2026) is left out of retrieval entirely.[/dim]\n")

    # Simulate top_k=2 retrieval without metadata filtering (leaving out the target Q1 2026 doc)
    retrieved_docs = [HALLUCINATION_CORPUS[0], HALLUCINATION_CORPUS[1]] 
    
    context_parts = []
    for d in retrieved_docs:
        context_parts.append(f"Source {d['id']} (Metadata: Year {d['metadata']['year']}, Q{d['metadata']['quarter']}): {d['content']}")
    context_text = "\n".join(context_parts)

    prompt_naive = f"""
    Answer the question based ONLY on the provided context.
    If the context does not contain the answer, say "I do not know".
    
    Context:
    {context_text}
    
    Question: {query}
    """
    run_llm_query(prompt_naive, "Naive RAG (top_k=2) with Metadata in Prompt")
    console.print()

    # --- APPROACH B: Pre-Filtering (Metadata Filtered Retrieval) ---
    console.print("[bold green]Approach B: Metadata-Filtered RAG[/bold green]")
    console.print("[dim]We extract filters (Year=2026, Q=1) first and restrict the DB query to match metadata.[/dim]")
    console.print("[dim]The database successfully returns the target document, ensuring zero hallucination.[/dim]\n")

    filters = extract_filters(query)
    console.print(f"[bold cyan]Step 1: Extracted Filters[/bold cyan] -> {filters}")
    
    # Programmatic filtering
    filtered_docs = [
        d for d in HALLUCINATION_CORPUS 
        if d['metadata']['year'] == filters.get('year') 
        and d['metadata']['quarter'] == filters.get('quarter')
    ]
    console.print(f"[bold cyan]Step 2: Database Filtered Retrieval[/bold cyan] -> Found {len(filtered_docs)} doc(s)\n")

    context_parts = []
    for d in filtered_docs:
        context_parts.append(f"Source {d['id']} (Metadata: Year {d['metadata']['year']}, Q{d['metadata']['quarter']}): {d['content']}")
    context_text = "\n".join(context_parts)

    prompt_filtered = f"""
    Answer the question based ONLY on the provided context.
    If the context does not contain the answer, say "I do not know".
    
    Context:
    {context_text}
    
    Question: {query}
    """
    run_llm_query(prompt_filtered, "Metadata-Filtered RAG")
    console.print("\n" + "="*80 + "\n")


def main():
    console.print(
        Panel.fit(
            "[bold yellow]Metadata Filtering Deep Dive Demonstration[/bold yellow]\n"
            "[dim]Showcasing the critical importance of pre-filtering for Hallucinations and Security.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    demo_hallucination_and_retrieval()

if __name__ == "__main__":
    main()
