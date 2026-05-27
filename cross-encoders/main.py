import textwrap
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from sentence_transformers import SentenceTransformer, CrossEncoder, util
import torch

console = Console()

def main():
    # Opening header
    console.print(
        Panel.fit(
            "[bold yellow]Cross-Encoder vs Bi-Encoder Prototype[/bold yellow]\n"
            "[dim]Demonstrating the precision of cross-encoders in semantic ranking.[/dim]\n"
            "[dim]Task: Rank documents for the query \"apple computer\"[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Data - Relational/Entity Swap (The "Logic Trap")
    query = "Does aspirin treat headaches?"
    docs = [
        "Aspirin is a highly effective medication used to treat headaches and fever.",
        "A severe headache is a known rare side effect of taking aspirin.",
        "To treat a headache, doctors often recommend aspirin or rest.",
        "Taking aspirin for a headache should be done with food to avoid stomach upset.",
        "Headaches are often caused by stress, not a lack of aspirin.",
        "Clinical trials show that aspirin treats headaches by reducing inflammation."
    ]

    # 1. Bi-Encoder (Fast but less precise)
    console.print(Rule("[bold]Bi-Encoder (Embedding-based Search)[/bold]", style="white"))
    console.print("[bold cyan]-- Encoding and Computing Cosine Similarity ----------------[/bold cyan]")
    
    bi_model = SentenceTransformer('all-MiniLM-L6-v2') 
    query_embedding = bi_model.encode(query, convert_to_tensor=True)
    doc_embeddings = bi_model.encode(docs, convert_to_tensor=True)
    
    hits = util.semantic_search(query_embedding, doc_embeddings, top_k=len(docs))[0]
    
    bi_results = []
    for hit in hits:
        bi_results.append({
            "doc": docs[hit['corpus_id']],
            "score": hit['score']
        })

    # 2. Cross-Encoder (Slow but highly precise)
    console.print(Rule("[bold]Cross-Encoder (Direct Interaction)[/bold]", style="white"))
    console.print("[bold magenta]-- Re-ranking Query-Document Pairs ------------------------[/bold magenta]")
    
    cross_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    cross_inp = [[query, doc] for doc in docs]
    cross_scores = cross_model.predict(cross_inp)
    
    cross_results = []
    for i in range(len(docs)):
        cross_results.append({
            "doc": docs[i],
            "score": cross_scores[i]
        })
    
    # Sort cross results by score
    cross_results = sorted(cross_results, key=lambda x: x['score'], reverse=True)

    # Output Comparison Table
    console.print(Rule("[bold yellow]Comparative Results[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title=f"Query: \"{query}\"", show_lines=True)
    table.add_column("Rank", justify="center", style="dim")
    table.add_column("Bi-Encoder (Cosine Similarity)", min_width=40)
    table.add_column("Cross-Encoder (Relevance Score)", min_width=40)

    # Logic to identify 'correct' (A treats B) vs 'incorrect' (B is side effect)
    def is_relevant(text):
        text = text.lower()
        # Relevant if it mentions aspirin treating or being used for headaches
        return ("treat" in text or "recommend" in text or "for a headache" in text) and "side effect" not in text and "not a lack" not in text

    for i in range(len(docs)):
        bi_doc = bi_results[i]['doc']
        cross_doc = cross_results[i]['doc']
        
        bi_text = f"[bold]{bi_doc[:60]}...[/bold]\n[dim]Score: {bi_results[i]['score']:.4f}[/dim]"
        cross_text = f"[bold]{cross_doc[:60]}...[/bold]\n[dim]Score: {cross_results[i]['score']:.4f}[/dim]"
        
        if is_relevant(bi_doc):
            bi_text = f"[green]{bi_text}[/green]"
        else:
            bi_text = f"[red]{bi_text}[/red]"
            
        if is_relevant(cross_doc):
            cross_text = f"[green]{cross_text}[/green]"
        else:
            cross_text = f"[red]{cross_text}[/red]"

        table.add_row(str(i+1), bi_text, cross_text)

    console.print(table)
    console.print()

if __name__ == "__main__":
    main()
