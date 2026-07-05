import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# --- Configuration & Corpus ---

DOCUMENTS = {
    "Doc1": "Guide to resolving memory leaks in Python 3.11: fixing garbage collection and optimizing objects.",
    "Doc2": "Troubleshooting RAM bloat in CPython (Python): resolving heap allocation bottlenecks and GC overhead.",
    "Doc3": "Python 3.11 release notes and changelog: memory management module updates and minor fixes.",
    "Doc4": "How to repair a leaky water hose in your garden: a quick DIY fix.",
    "Doc5": "Java Garbage Collection and Memory Management: resolving heap leaks in JVM.",
    "Doc6": "A study of RAM hardware architectures: physical memory caches and throughput optimization.",
    "Doc7": "Automotive repair manual: fixing oil leaks in high-performance engines.",
    "Doc8": "Python 3.11 memory leak fix in the asyncio event loop.",
    "Doc9": "Optimizing memory consumption in Go applications: tracing memory leaks using pprof.",
    "Doc10": "Debugging memory leak issues in older Python 2.7 environments.",
}

# --- Simulated Concept Space Map ---
# This dictionary maps vocab terms to coordinates in a 5-dimensional concept space:
# Dimensions: [0: Programming Language, 1: Specific Version, 2: Memory System, 3: Anomaly Type, 4: Action/Resolution]
CONCEPT_MAP = {
    # Programming languages / environments
    "python": [1.0, 0.0, 0.0, 0.0, 0.0],
    "cpython": [1.0, 0.0, 0.0, 0.0, 0.0],
    "java": [0.2, 0.0, 0.0, 0.0, 0.0],
    "jvm": [0.2, 0.0, 0.0, 0.0, 0.0],
    "go": [0.2, 0.0, 0.0, 0.0, 0.0],
    "golang": [0.2, 0.0, 0.0, 0.0, 0.0],
    
    # Specific software versions
    "3.11": [0.0, 1.0, 0.0, 0.0, 0.0],
    "3.11.2": [0.0, 1.0, 0.0, 0.0, 0.0],
    "2.7": [0.0, 0.2, 0.0, 0.0, 0.0],
    "3.9": [0.0, 0.4, 0.0, 0.0, 0.0],
    
    # Memory management systems
    "memory": [0.0, 0.0, 1.0, 0.0, 0.0],
    "ram": [0.0, 0.0, 1.0, 0.0, 0.0],
    "heap": [0.0, 0.0, 1.0, 0.0, 0.0],
    "gc": [0.0, 0.0, 0.8, 0.0, 0.0],
    "garbage": [0.0, 0.0, 0.8, 0.0, 0.0],
    "collection": [0.0, 0.0, 0.8, 0.0, 0.0],
    
    # Anomaly / Fault types
    "leak": [0.0, 0.0, 0.0, 1.0, 0.0],
    "leaks": [0.0, 0.0, 0.0, 1.0, 0.0],
    "leaky": [0.0, 0.0, 0.0, 0.9, 0.0],
    "bloat": [0.0, 0.0, 0.0, 1.0, 0.0],
    "consumption": [0.0, 0.0, 0.0, 0.8, 0.0],
    "bottlenecks": [0.0, 0.0, 0.0, 0.8, 0.0],
    "accumulation": [0.0, 0.0, 0.0, 0.9, 0.0],
    
    # Action / Resolution methods
    "fix": [0.0, 0.0, 0.0, 0.0, 1.0],
    "fixes": [0.0, 0.0, 0.0, 0.0, 1.0],
    "fixing": [0.0, 0.0, 0.0, 0.0, 1.0],
    "resolving": [0.0, 0.0, 0.0, 0.0, 1.0],
    "troubleshooting": [0.0, 0.0, 0.0, 0.0, 1.0],
    "debugging": [0.0, 0.0, 0.0, 0.0, 1.0],
    "optimizing": [0.0, 0.0, 0.0, 0.0, 1.0],
    "optimization": [0.0, 0.0, 0.0, 0.0, 1.0],
    "repair": [0.0, 0.0, 0.0, 0.0, 0.8],
}

VERDICT_MAP = {
    "Doc8": ("[bold green]Consensus (Perfect Match)[/bold green]", "Top ranker in both search engines; exact keyword and semantic alignment."),
    "Doc10": ("[bold green]Consensus (Python 2.7)[/bold green]", "Strong relevance in both; wrong Python version but same core concepts."),
    "Doc1": ("[bold green]Consensus (Python 3.11)[/bold green]", "Strong relevance in both; perfect version match and conceptual alignment."),
    "Doc3": ("[bold cyan]Keyword Rescue[/bold cyan]", "Exact 'Python 3.11' & 'fixes' matches. Rescued from poor semantic rank (#6)."),
    "Doc2": ("[bold magenta]Semantic Rescue[/bold magenta]", "No query words matched! Rescued from poor keyword rank (#7) due to 'CPython RAM bloat' concept."),
    "Doc9": ("[dim]Go Language Match[/dim]", "Irrelevant language (Go). Suppressed by lack of keyword relevance."),
    "Doc4": ("[bold red]Keyword Noise Suppressed[/bold red]", "Garden hose DIY leak fix. Promoted by keyword search but demoted by semantic filter."),
    "Doc5": ("[bold red]Semantic Noise Suppressed[/bold red]", "Java JVM heap leaks. Matches memory/leak concepts but pushed down due to wrong language."),
    "Doc6": ("[dim]Irrelevant Noise[/dim]", "Hardware RAM architectures. Irrelevant topic, pushed to the bottom."),
    "Doc7": ("[dim]Irrelevant Noise[/dim]", "Automotive oil leak manual. Irrelevant topic, pushed to the bottom."),
}

# --- Core Logic ---

def text_to_concept_vector(text):
    """Tokenizes and represents any text string as a normalized concept vector."""
    words = re.findall(r'[a-zA-Z0-9\.]+', text.lower())
    vec = np.zeros(5)
    for word in words:
        if word in CONCEPT_MAP:
            vec += np.array(CONCEPT_MAP[word])
    norm = np.linalg.norm(vec)
    if norm > 0:
        return vec / norm
    return vec

def keyword_search(query):
    """Traditional keyword search using TF-IDF."""
    # We use a custom token pattern to avoid splitting '3.11' into '11'
    v = TfidfVectorizer(token_pattern=r'(?u)\b[a-zA-Z0-9_.]+\b', stop_words='english')
    matrix = v.fit_transform(list(DOCUMENTS.values()))
    q_term_vec = v.transform([query])
    scores = cosine_similarity(q_term_vec, matrix).flatten()
    doc_ids = list(DOCUMENTS.keys())
    ranked = sorted([(doc_ids[i], scores[i]) for i in range(len(doc_ids)) if scores[i] > 0], key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in ranked]

def semantic_search(query):
    """Dense/semantic vector-space search using the mapped concept vectors."""
    q_vec = text_to_concept_vector(query)
    scores = []
    for doc_id, doc_text in DOCUMENTS.items():
        d_vec = text_to_concept_vector(doc_text)
        sim = np.dot(q_vec, d_vec) if np.linalg.norm(d_vec) > 0 else 0.0
        if sim > 0:
            scores.append((doc_id, sim))
    ranked = sorted(scores, key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in ranked]

def reciprocal_rank_fusion(kw_results, sem_results, k=10):
    """Applies Reciprocal Rank Fusion formula: Score(d) = sum( 1 / (k + rank(d)) )"""
    scores = {}
    for rank, doc_id in enumerate(kw_results, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    for rank, doc_id in enumerate(sem_results, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def main():
    console = Console()
    
    # 1. Header
    console.print(
        Panel.fit(
            "[bold yellow]Reciprocal Rank Fusion (RRF) Demonstrator[/bold yellow]\n"
            "[dim]Comparing Keyword (TF-IDF) vs Semantic (Concept-Space Vector) vs Fused Rankings.[/dim]\n"
            "[dim]Query: 'Python 3.11 memory leak fix' | Corpus: 10 diverse documents[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    
    # Get rankings
    query = "Python 3.11 memory leak fix"
    keyword_results = keyword_search(query)
    semantic_results = semantic_search(query)
    fused_results = reciprocal_rank_fusion(keyword_results, semantic_results, k=10)
    
    # 2. Side-by-Side Comparison Table
    console.print(Rule("[bold white]Search Engine Run Results[/bold white]", style="white"))
    console.print()
    
    table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Keyword Ranker (TF-IDF) [Cyan]", style="cyan")
    table.add_column("Semantic Ranker (Conceptual) [Magenta]", style="magenta")
    table.add_column("Fused Ranking (RRF) [Bold Yellow]", style="bold yellow")
    
    max_rows = max(len(keyword_results), len(semantic_results), len(fused_results))
    
    for i in range(max_rows):
        kw_doc = keyword_results[i] if i < len(keyword_results) else "-"
        sm_doc = semantic_results[i] if i < len(semantic_results) else "-"
        fs_doc = fused_results[i][0] if i < len(fused_results) else "-"
        fs_score = f"[Score: {fused_results[i][1]:.4f}]" if i < len(fused_results) else ""
        
        table.add_row(
            str(i + 1),
            f"{kw_doc} ({DOCUMENTS.get(kw_doc, '')[:28]}...)" if kw_doc != "-" else "-",
            f"{sm_doc} ({DOCUMENTS.get(sm_doc, '')[:28]}...)" if sm_doc != "-" else "-",
            f"{fs_doc} {fs_score}" if fs_doc != "-" else "-"
        )
        
    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
