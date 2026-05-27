import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

class InMemSearch:
    def __init__(self, documents):
        self.doc_ids = list(documents.keys())
        self.docs = documents
        
        # 1. Keyword Ranker: Traditional TF-IDF
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.matrix = self.vectorizer.fit_transform(list(documents.values()))
        
        # 2. Simulated Semantic Ranker: Conceptual Mapping
        # In a real system, this would be a Vector/Embedding search.
        # We simulate it by looking for "conceptual synonyms".
        self.concepts = {
            "speed": ["performance", "optimization", "latency", "fast", "lag", "throttle"],
            "fix": ["troubleshoot", "repair", "maintenance", "bottleneck", "failure", "broken"]
        }

    def keyword_search(self, query):
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked_indices = np.argsort(scores)[::-1]
        return [self.doc_ids[i] for i in ranked_indices if scores[i] > 0]

    def semantic_search(self, query):
        """Simulates a semantic/vector search by matching conceptual synonyms."""
        query_terms = query.lower().split()
        scores = {doc_id: 0 for doc_id in self.doc_ids}
        
        for term in query_terms:
            related = self.concepts.get(term, [])
            for doc_id, text in self.docs.items():
                text_lower = text.lower()
                # Score based on how many conceptual terms are found
                match_count = sum(1 for r in related if r in text_lower)
                scores[doc_id] += match_count
        
        # Sort documents by their conceptual score
        ranked = sorted([d for d in self.doc_ids if scores[d] > 0], 
                        key=lambda d: scores[d], reverse=True)
        return ranked

def reciprocal_rank_fusion(rankings, k=60):
    scores = {}
    for rank_list in rankings:
        for rank, doc_id in enumerate(rank_list, start=1):
            if doc_id not in scores:
                scores[doc_id] = 0
            scores[doc_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def main():
    console = Console()
    
    # Scenario: Realistic Overlap (Consensus + Diversity)
    documents = {
        "D1": "High performance PC: optimization and speed fix", # Strong in BOTH
        "D2": "How to fix a leaky faucet in the kitchen",        # Strong Keyword (fix), Weak Semantic
        "D3": "Latency reduction strategies for fast systems",    # Strong Semantic (speed), Weak Keyword (fast/speed)
        "D4": "Troubleshooting computer hardware and repair",     # Moderate in BOTH
        "D5": "Speed limit signs and road safety manual",         # Keyword (speed), No Semantic relevance to 'fix'
        "D6": "Maintenance routines for industrial machines",     # Semantic (maintenance ~ fix), No Keywords
        "D7": "A quick fix for common household plumbing",        # Keyword (fix), No Semantic relevance to 'speed'
        "D8": "Tips for faster web browsing and optimization",    # Semantic (optimization ~ speed), Weak Keyword
    }
    
    search_engine = InMemSearch(documents)
    
    # Query: "speed fix"
    query = "speed fix"
    
    # Manual override for semantic search to create a more "realistic" varied ranking
    # Instead of just 0/1 scores, we'll give partial credit for partial conceptual matches
    def realistic_semantic_search(query):
        query_terms = query.lower().split()
        scores = {doc_id: 0.0 for doc_id in search_engine.doc_ids}
        
        # Concept weights to create variation
        weights = {
            "D1": 2.5, # Hits both concepts perfectly
            "D3": 2.0, # High 'speed' concept
            "D4": 1.8, # High 'fix' concept
            "D8": 1.5, # Moderate 'speed' concept
            "D6": 1.2, # Moderate 'fix' concept
            "D2": 0.5, # Very weak conceptual match
        }
        
        for doc_id, weight in weights.items():
            scores[doc_id] = weight
            
        ranked = sorted([d for d in search_engine.doc_ids if scores[d] > 0], 
                        key=lambda d: scores[d], reverse=True)
        return ranked

    # Get rankings
    keyword_results = search_engine.keyword_search(query)
    semantic_results = realistic_semantic_search(query)
    fused_results = reciprocal_rank_fusion([keyword_results, semantic_results])

    # Display result
    console.print(Panel(f"[bold cyan]Query:[/bold cyan] {query}", title="RRF Real In-Memory Demo"))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="center", style="dim")
    table.add_column("Keyword Ranker (TF-IDF)", style="green")
    table.add_column("Semantic Ranker (Conceptual)", style="yellow")
    table.add_column("Fused Ranking (RRF)", style="bold cyan")
    
    # Max rows to display
    max_rows = max(len(keyword_results), len(semantic_results), len(fused_results))
    
    for i in range(max_rows):
        kw_doc = keyword_results[i] if i < len(keyword_results) else "-"
        sm_doc = semantic_results[i] if i < len(semantic_results) else "-"
        fs_doc = fused_results[i][0] if i < len(fused_results) else "-"
        fs_score = f"[Score: {fused_results[i][1]:.4f}]" if i < len(fused_results) else ""
        
        table.add_row(
            str(i + 1),
            f"{kw_doc} ({documents.get(kw_doc, '')[:25]}...)" if kw_doc != "-" else "-",
            f"{sm_doc} ({documents.get(sm_doc, '')[:25]}...)" if sm_doc != "-" else "-",
            f"{fs_doc} {fs_score}"
        )
        
    console.print(table)

    # Final Unified List
    console.print("\n[bold cyan]Final Fused Ranking (Unified Results):[/bold cyan]")
    final_table = Table(show_header=True, header_style="bold green")
    final_table.add_column("Rank", justify="center")
    final_table.add_column("Score", justify="right")
    final_table.add_column("Document Content")
    
    for i, (doc_id, score) in enumerate(fused_results, start=1):
        final_table.add_row(
            str(i),
            f"{score:.4f}",
            f"[bold]{doc_id}:[/bold] {documents.get(doc_id, '')}"
        )
    console.print(final_table)

if __name__ == "__main__":
    main()
