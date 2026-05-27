import os
import json
import textwrap
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize Rich Console
console = Console()

# Initialize the Gemini client
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# 1. Mock Dataset - Content is AMBIGUOUS! Year/Quarter only exists in Metadata.
DOCUMENTS = [
    {
        "id": "DOC_001",
        "content": "Financial Summary: Total revenue reached $10M with 15% growth.",
        "metadata": {"year": 2025, "quarter": 1}
    },
    {
        "id": "DOC_002",
        "content": "Financial Summary: Total revenue reached $12M with 10% growth.",
        "metadata": {"year": 2025, "quarter": 2}
    },
    {
        "id": "DOC_003",
        "content": "Financial Summary: Total revenue reached $15M with 5% growth.",
        "metadata": {"year": 2026, "quarter": 1}
    }
]

def extract_filters(query: str):
    """Uses Gemini to extract structured filter criteria."""
    prompt = f"""
    Extract filtering criteria from the user query.
    Query: "{query}"
    Return a JSON object with 'year' (int) and 'quarter' (int).
    For 'quarter', convert strings like 'Q1' or 'first quarter' into the corresponding integer (1-4).
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
        # Ensure year and quarter are integers if they exist
        if 'year' in data and data['year'] is not None:
            data['year'] = int(data['year'])
        if 'quarter' in data and data['quarter'] is not None:
            data['quarter'] = int(data['quarter'])
        return data
    except Exception as e:
        console.print(f"[bold red]Error parsing filters:[/bold red] {e}")
        return {}

def generate_answer(query: str, context_docs: list, label: str, include_metadata: bool = False):
    if not context_docs:
        return "[bold red]No documents matched your filters.[/bold red]"
        
    context_parts = []
    for d in context_docs:
        meta_str = f" (Metadata: Year {d['metadata']['year']}, Q{d['metadata']['quarter']})" if include_metadata else ""
        context_parts.append(f"Source {d['id']}{meta_str}: {d['content']}")
    
    context_text = "\n".join(context_parts)
    
    prompt = f"""
    Answer the question based ONLY on the provided context.
    If you see multiple sources and can't be sure which one is correct for the specific time mentioned in the query, 
    either say you don't know or explain the ambiguity.
    
    Context:
    {context_text}
    
    Question: {query}
    """
    
    # Display model input
    console.print(Panel(Text(f"PROMPT:\n{prompt.strip()}", style="blue"), title=f"[bold bright_black]{label} Input[/bold bright_black]", border_style="bright_black"))
    
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    response_text = response.text.strip()
    
    # Display model output
    console.print(Panel(Text(f"ASSISTANT: {response_text}", style="green italic"), title="[bold bright_black]Model Response[/bold bright_black]", border_style="bright_black"))
    
    return response_text

def main():
    console.print(
        Panel.fit(
            "[bold yellow]Metadata Filtering vs. Naive RAG[/bold yellow]\n"
            "[dim]Goal: Demonstrate how filters prevent 'Context Contamination' and Hallucinations.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    query = "What was the revenue in Q1 2026?"
    console.print(f"[bold]User Query:[/bold] [cyan]{query}[/cyan]\n")

    # --- APPROACH 1: NAIVE RAG ------------------------------
    console.print(Rule("[bold red]Approach 1: Naive RAG (No Filters)[/bold red]", style="red"))
    console.print("[dim]Retrieves all 'Financial Summary' docs because they match the keywords.[/dim]\n")
    
    # In naive RAG, the retriever finds all semantically similar documents.
    # Here we simulate that by giving it everything.
    naive_docs = DOCUMENTS 
    generate_answer(query, naive_docs, "Naive RAG", include_metadata=False)
    
    console.print()

    # --- APPROACH 2: METADATA FILTERING ---------------------
    console.print(Rule("[bold green]Approach 2: Metadata Filtering[/bold green]", style="green"))
    console.print("[dim]1. Extract filter from query. 2. Filter DB. 3. Send only relevant doc to LLM.[/dim]\n")
    
    filters = extract_filters(query)
    console.print(f"[bold cyan]Step 1: Extracted Filters[/bold cyan] -> {filters}")
    
    filtered_docs = [
        d for d in DOCUMENTS 
        if d['metadata']['year'] == filters.get('year') 
        and d['metadata']['quarter'] == filters.get('quarter')
    ]
    console.print(f"[bold cyan]Step 2: Filtered Database[/bold cyan] -> Found {len(filtered_docs)} document(s)\n")
    
    # In Filtered RAG, the LLM is only given the context that passed the metadata check.
    # We also include metadata in context to be extra sure (best practice).
    generate_answer(query, filtered_docs, "Metadata Filtered RAG", include_metadata=True)
    console.print()

if __name__ == "__main__":
    main()
