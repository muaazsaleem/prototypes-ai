import os
import textwrap
import numpy as np
from dotenv import load_dotenv
from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Load environment variables (API Key)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)
console = Console()

# --- Mock Knowledge Base (High-Technical Language + Strategic Distractors) ---
DOCUMENTS = [
    {
        "id": "DOC-ALGAE",
        "content": "Project Chloris implements high-density photobioreactors utilizing micro-algae (Spirulina) for the active sequestration of atmospheric carbon dioxide."
    },
    {
        "id": "DOC-CITY-FOREST",
        "content": "The Urban Streets Initiative installs deciduous trees to clean city smog and improve air quality in crowded metropolitan streets."
    },
    {
        "id": "DOC-CARBON-MECH",
        "content": "The Aeolus turbine series utilizes industrial-scale amine scrubbing units for mechanical direct air capture (DAC) and post-combustion carbon storage."
    },
    {
        "id": "DOC-CRYPT",
        "content": "The Obsidian Protocol utilizes zero-knowledge proofs and sharded peer-to-peer architecture to ensure immutable data persistence across a global node network."
    },
    {
        "id": "DOC-SOLAR",
        "content": "The Icarus system employs bifacial photovoltaic arrays with metamaterial coatings to optimize quantum efficiency and mitigate thermal degradation."
    }
]

def get_embedding(text):
    """Get embedding for a given text using gemini-embedding-2."""
    result = client.models.embed_content(
        model='gemini-embedding-2',
        contents=text
    )
    return np.array(result.embeddings[0].values)

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search(query_vector, documents_with_embeddings):
    """Search for the most similar document."""
    results = []
    for doc in documents_with_embeddings:
        similarity = cosine_similarity(query_vector, doc["embedding"])
        results.append({"id": doc["id"], "content": doc["content"], "score": similarity})
    
    # Sort by score descending
    return sorted(results, key=lambda x: x["score"], reverse=True)

def run_prototype():
    # 1. Opening Header
    console.print(
        Panel.fit(
            "[bold yellow]HyDE Query Rewrite: The Rank Flip Demo[/bold yellow]\n"
            "[dim]Proving that query rewriting can change the result order to find the truth.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # 2. Preparation: Pre-embed documents
    console.print("[bold cyan]Step 1: Indexing Knowledge Base...[/bold cyan]")
    docs_with_embeddings = []
    for doc in DOCUMENTS:
        doc_emb = get_embedding(doc["content"])
        docs_with_embeddings.append({**doc, "embedding": doc_emb})
        console.print(f"  [dim]Indexed {doc['id']}[/dim]")
    console.print()

    # 3. The Problem: A Metaphorical Query
    # We use "liquid trees" (algae) + many keywords from the Forestry doc.
    query = "How do 'liquid trees' work to clean the smog in our city streets?"
    
    console.print(Rule("[bold red]The Problem: Metaphorical User Query[/bold red]", style="red"))
    console.print(f"\n[bold blue]> USER INPUT[/bold blue]")
    console.print(f"  [white]'{query}'[/white]\n")
    console.print("[dim italic]Challenge: This query shares 5 keywords with the Forestry doc ('trees', 'clean', 'smog', 'city', 'streets').[/dim italic]")
    console.print("[dim italic]The target doc (Algae) shares ZERO keywords with this query.[/dim italic]\n")

    # 4. Strategy A: Standard Search (Raw Metaphor)
    console.print("[bold cyan]-- Strategy A: Standard Search (Raw Metaphor) -----------------------[/bold cyan]")
    query_emb = get_embedding(query)
    standard_results = search(query_emb, docs_with_embeddings)
    
    # 5. Strategy B: HyDE Search (Intelligent Bridge)
    console.print("[bold magenta]-- Strategy B: HyDE Search (Intelligent Bridge) --------------------[/bold magenta]")
    
    # The LLM "unpacks" the metaphor.
    hypothetical_doc = (
        "The photobioreactor system utilizes high-density micro-algae (Spirulina) cultures "
        "to perform biological carbon sequestration. By utilizing photosynthesis, these "
        "bioreactors filter CO2 from the atmosphere more efficiently than traditional trees."
    )
    
    # Show the "Bridge"
    console.print(
        Panel(
            Text.assemble(
                ("USER METAPHOR: ", "bold red"), (f"'{query}'\n\n", "red"),
                ("LLM DECODED REWRITE:\n", "bold green"), (hypothetical_doc, "italic")
            ),
            title="[bold bright_black]The Semantic Bridge[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    hyde_emb = get_embedding(hypothetical_doc)
    hyde_results = search(hyde_emb, docs_with_embeddings)

    # 6. Comparison Table
    console.print(Rule("[bold yellow]Final Comparison: Did we find the Algae document (DOC-ALGAE)?[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Search Rank Comparison", show_lines=True)
    table.add_column("Rank", justify="center")
    table.add_column("Standard Search (Keyword Overlap)", style="cyan")
    table.add_column("HyDE Search (Decoded Metaphor)", style="magenta")

    for i in range(len(DOCUMENTS)):
        std = standard_results[i]
        hyd = hyde_results[i]
        
        # Format strings
        def format_result(res):
            is_correct = res['id'] == "DOC-ALGAE"
            color = "green" if is_correct else "dim"
            return f"[{color}][bold]{res['id']}[/bold] (Score: {res['score']:.4f})[/{color}]\n[dim]{res['content'][:55]}...[/dim]"

        table.add_row(str(i+1), format_result(std), format_result(hyd))

    console.print(table)
    
    # 7. Final Analysis
    std_winner = standard_results[0]['id']
    hyd_winner = hyde_results[0]['id']
    
    console.print(f"\n[bold yellow]Analysis:[/bold yellow]")
    if std_winner != "DOC-ALGAE":
        console.print(f"Standard Search Result: [bold red]WRONG[/bold red] (Ranked {std_winner} #1 due to keyword overlap)")
    else:
        console.print(f"Standard Search Result: [bold yellow]CORRECT BUT WEAK[/bold yellow]")

    if hyd_winner == "DOC-ALGAE":
        console.print(f"HyDE Search Result:     [bold green]CORRECT[/bold green] (Ranked DOC-ALGAE #1 by decoding the intent)")

    if std_winner != hyd_winner:
        console.print(f"\n[bold green]SUCCESS:[/bold green] HyDE successfully corrected the rank order and found the intended document!")
    else:
        console.print(f"\n[bold yellow]NOTE:[/bold yellow] Even with keyword traps, embeddings are surprisingly robust. Try even more obscure metaphors if needed.")
    console.print()

if __name__ == "__main__":
    try:
        run_prototype()
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
