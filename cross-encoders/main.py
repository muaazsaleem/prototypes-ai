import argparse
import sys
import textwrap
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from sentence_transformers import SentenceTransformer, CrossEncoder, util

console = Console()

_models = {}

def get_bi_model():
    if "bi" not in _models:
        with console.status("[bold cyan]Loading Bi-Encoder model ('all-MiniLM-L6-v2')...[/bold cyan]"):
            _models["bi"] = SentenceTransformer('all-MiniLM-L6-v2')
    return _models["bi"]

def get_cross_model():
    if "cross" not in _models:
        with console.status("[bold magenta]Loading Cross-Encoder model ('mixedbread-ai/mxbai-rerank-large-v1')...[/bold magenta]"):
            _models["cross"] = CrossEncoder('mixedbread-ai/mxbai-rerank-large-v1')
    return _models["cross"]

SCENARIOS = {
    "1": {
        "title": "Lexical & Semantic Ambiguity (Fruit vs. Tech)",
        "query": "apple computer",
        "description": "Bi-encoders are heavily biased by keyword overlap. When searching for 'apple computer', documents containing the word 'apple' (like apple fruit or pie) align strongly in the vector space. Cross-encoders use joint attention to recognize that 'computer' restricts the meaning of 'apple' to technology.",
        "docs": [
            {"text": "The new MacBook Pro is a powerful Apple computer built for creative professionals.", "is_relevant": True},
            {"text": "An apple a day keeps the doctor away, especially if it is a fresh, organic red delicious apple.", "is_relevant": False},
            {"text": "Apple Inc. is expected to announce new hardware products at its upcoming keynote.", "is_relevant": True},
            {"text": "I baked a delicious homemade apple pie with a crispy, golden-brown crust.", "is_relevant": False},
            {"text": "Computers are complex machines; remember to eat a healthy apple while working on them.", "is_relevant": False},
            {"text": "The stock price of Apple rose after they announced their latest high-performance computers.", "is_relevant": True}
        ],
        "analysis": (
            "[bold cyan]Why the Bi-Encoder struggled:[/bold cyan]\n"
            "• The document [red]'Computers are complex machines; remember to eat a healthy apple...'[/red] is ranked highly because it contains both of the query terms ('apple' and 'computer') literally, even though their relationship is purely coincidental and irrelevant.\n"
            "• It also gives moderate similarity scores to fruit-related documents ('apple pie', 'apple a day') because the word 'apple' has high vector similarity with the query.\n\n"
            "[bold magenta]Why the Cross-Encoder succeeded:[/bold magenta]\n"
            "• By performing token-to-token cross-attention between the query and the document simultaneously, it realizes that 'computer' in the query does not relate to 'pie' or 'doctor' in the documents.\n"
            "• It outputs extremely low scores (e.g., 0.00 to 0.27) for the irrelevant fruit articles and coincidental matches, while scoring actual technology-related articles highly (above 0.75), providing a crystal-clear separation margin."
        )
    },
    "2": {
        "title": "Logical Relation & Negation (The 'Logic Trap')",
        "query": "Does aspirin treat headaches?",
        "description": "Bi-encoders struggle with semantic relationships (causes vs. treats) and negation because they compress sentences into a single vector, losing syntactical directionality. Cross-encoders maintain token-to-token interactions, accurately resolving complex logic.",
        "docs": [
            {"text": "Clinical trials show that aspirin treats headaches by reducing inflammation.", "is_relevant": True},
            {"text": "A severe headache is a known rare side effect of taking aspirin.", "is_relevant": False},
            {"text": "To treat a headache, doctors often recommend aspirin or rest.", "is_relevant": True},
            {"text": "Headaches are often caused by stress, not a lack of aspirin.", "is_relevant": False},
            {"text": "Taking aspirin for a headache should be done with food to avoid stomach upset.", "is_relevant": True},
            {"text": "Aspirin can cause stomach bleeding, which is a far worse issue than a mild headache.", "is_relevant": False}
        ],
        "analysis": (
            "[bold cyan]Why the Bi-Encoder struggled:[/bold cyan]\n"
            "• It scores [red]'A severe headache is a known rare side effect of taking aspirin'[/red] extremely high. This is because the sentence contains 'aspirin' and 'headache', completely ignoring the causal direction (aspirin causing a headache rather than treating it).\n"
            "• It also fails to discount the negation in [red]'not a lack of aspirin'[/red] because the keyword overlap is high.\n\n"
            "[bold magenta]Why the Cross-Encoder succeeded:[/bold magenta]\n"
            "• The cross-attention layers easily resolve the syntactic dependency between 'aspirin', 'treats', and 'headache'.\n"
            "• It correctly identifies that a 'side effect' of headache means aspirin causes headache, assigning it a much lower relevance score."
        )
    },
    "3": {
        "title": "Asymmetric Directional Search (Source vs. Destination)",
        "query": "flight from Boston to New York",
        "description": "Directional queries are notoriously difficult for bi-encoders. Since the vocabulary of 'Boston to New York' and 'New York to Boston' is identical, their dense embeddings are nearly identical. Cross-encoders capture precise sequence order and prepositions.",
        "docs": [
            {"text": "This direct flight from Boston to New York leaves daily at 9:00 AM.", "is_relevant": True},
            {"text": "We offer daily high-speed flights from New York to Boston starting at $99.", "is_relevant": False},
            {"text": "Amtrak's Acela Express provides fast train travel between Boston and New York.", "is_relevant": False},
            {"text": "Enjoy our luxurious business-class flight from Boston to New York with free Wi-Fi.", "is_relevant": True},
            {"text": "If you are flying out of New York, you can easily catch an evening flight to Boston.", "is_relevant": False},
            {"text": "Flights to other major East Coast cities, including Boston and New York, are on sale.", "is_relevant": False}
        ],
        "analysis": (
            "[bold cyan]Why the Bi-Encoder struggled:[/bold cyan]\n"
            "• It cannot differentiate between the source and destination. The sentence [red]'flights from New York to Boston'[/red] gets nearly the same similarity score as the correct one because the word vectors for 'Boston', 'New York', and 'flight' dominate the sentence embedding.\n"
            "• It also scores train travel highly because it mentions 'Boston' and 'New York' in a transit context.\n\n"
            "[bold magenta]Why the Cross-Encoder succeeded:[/bold magenta]\n"
            "• It tracks word order and syntactic relations. It understands that 'from Boston' specifies the origin and 'to New York' specifies the destination.\n"
            "• It clearly downgrades the reverse flight ('New York to Boston') and train-based alternatives, placing only the genuine matching flights at the very top."
        )
    }
}

def run_scenario(scenario_id, scenario_data):
    query = scenario_data["query"]
    docs = scenario_data["docs"]
    title = scenario_data["title"]
    description = scenario_data["description"]
    
    console.print(Rule(f"[bold yellow]Scenario {scenario_id}: {title}[/bold yellow]", style="yellow"))
    console.print()
    console.print(f"[bold]Query:[/bold] \"{query}\"")
    console.print(f"[bold]Concept:[/bold] [dim]{description}[/dim]")
    console.print()
    
    bi_model = get_bi_model()
    cross_model = get_cross_model()
    
    doc_texts = [d["text"] for d in docs]
    query_emb = bi_model.encode(query, convert_to_tensor=True)
    doc_embs = bi_model.encode(doc_texts, convert_to_tensor=True)
    
    hits = util.semantic_search(query_emb, doc_embs, top_k=len(docs))[0]
    
    bi_results = []
    for hit in hits:
        idx = hit['corpus_id']
        bi_results.append({
            "text": docs[idx]["text"],
            "score": hit['score'],
            "is_relevant": docs[idx].get("is_relevant")
        })
        
    cross_inp = [[query, txt] for txt in doc_texts]
    cross_scores = cross_model.predict(cross_inp)
    
    cross_results = []
    for i in range(len(docs)):
        cross_results.append({
            "text": docs[i]["text"],
            "score": cross_scores[i],
            "is_relevant": docs[i].get("is_relevant")
        })
    cross_results = sorted(cross_results, key=lambda x: x['score'], reverse=True)
    
    table = Table(title=f"Comparison for Query: \"{query}\"", show_lines=True)
    table.add_column("Rank", justify="center", style="dim", width=6)
    table.add_column("Bi-Encoder (Cosine Similarity)", min_width=45)
    table.add_column("Cross-Encoder (Relevance Score)", min_width=45)
    
    for i in range(len(docs)):
        bi_res = bi_results[i]
        cr_res = cross_results[i]
        
        bi_text = bi_res["text"]
        bi_score = bi_res["score"]
        bi_rel = bi_res["is_relevant"]
        
        cr_text = cr_res["text"]
        cr_score = cr_res["score"]
        cr_rel = cr_res["is_relevant"]
        
        bi_wrapped = "\n".join(textwrap.wrap(bi_text, width=42))
        cr_wrapped = "\n".join(textwrap.wrap(cr_text, width=42))
        
        bi_cell = f"[bold]{bi_wrapped}[/bold]\n[dim]Score: {bi_score:.4f}[/dim]"
        cr_cell = f"[bold]{cr_wrapped}[/bold]\n[dim]Score: {cr_score:.4f}[/dim]"
        
        if bi_rel is True:
            bi_cell = f"[green]{bi_cell}[/green]"
        elif bi_rel is False:
            bi_cell = f"[red]{bi_cell}[/red]"
            
        if cr_rel is True:
            cr_cell = f"[green]{cr_cell}[/green]"
        elif cr_rel is False:
            cr_cell = f"[red]{cr_cell}[/red]"
            
        table.add_row(str(i+1), bi_cell, cr_cell)
        
    console.print(table)
    console.print()
    
    if "analysis" in scenario_data:
        console.print(
            Panel(
                scenario_data["analysis"],
                title="[bold yellow]Deep-Dive Analysis[/bold yellow]",
                border_style="yellow",
                padding=(1, 2)
            )
        )
        console.print()

def run_custom_scenario(query, doc_texts):
    console.print(Rule("[bold yellow]Custom Scenario[/bold yellow]", style="yellow"))
    console.print()
    console.print(f"[bold]Query:[/bold] \"{query}\"")
    console.print()
    
    bi_model = get_bi_model()
    cross_model = get_cross_model()
    
    query_emb = bi_model.encode(query, convert_to_tensor=True)
    doc_embs = bi_model.encode(doc_texts, convert_to_tensor=True)
    
    hits = util.semantic_search(query_emb, doc_embs, top_k=len(doc_texts))[0]
    
    bi_results = []
    for hit in hits:
        idx = hit['corpus_id']
        bi_results.append({
            "text": doc_texts[idx],
            "score": hit['score']
        })
        
    cross_inp = [[query, txt] for txt in doc_texts]
    cross_scores = cross_model.predict(cross_inp)
    
    cross_results = []
    for i in range(len(doc_texts)):
        cross_results.append({
            "text": doc_texts[i],
            "score": cross_scores[i]
        })
    cross_results = sorted(cross_results, key=lambda x: x['score'], reverse=True)
    
    table = Table(title=f"Comparison for Custom Query: \"{query}\"", show_lines=True)
    table.add_column("Rank", justify="center", style="dim", width=6)
    table.add_column("Bi-Encoder (Cosine Similarity)", min_width=45)
    table.add_column("Cross-Encoder (Relevance Score)", min_width=45)
    
    for i in range(len(doc_texts)):
        bi_res = bi_results[i]
        cr_res = cross_results[i]
        
        bi_text = bi_res["text"]
        bi_score = bi_res["score"]
        
        cr_text = cr_res["text"]
        cr_score = cr_res["score"]
        
        bi_wrapped = "\n".join(textwrap.wrap(bi_text, width=42))
        cr_wrapped = "\n".join(textwrap.wrap(cr_text, width=42))
        
        bi_cell = f"[bold white]{bi_wrapped}[/bold white]\n[dim cyan]Score: {bi_score:.4f}[/dim cyan]"
        cr_cell = f"[bold white]{cr_wrapped}[/bold white]\n[dim magenta]Score: {cr_score:.4f}[/dim magenta]"
            
        table.add_row(str(i+1), bi_cell, cr_cell)
        
    console.print(table)
    console.print()
    
    analysis_text = (
        "[bold cyan]Understanding the Results:[/bold cyan]\n"
        "• [bold cyan]Bi-Encoder (Cosine Similarity):[/bold cyan] Usually ranges between -1.0 and 1.0 (mostly 0.2 to 0.9 for relevant terms). It represents structural and keyword similarity based on independent vector mappings.\n"
        "• [bold magenta]Cross-Encoder (Relevance Score):[/bold magenta] Bounded similarity probability/sigmoid scores between 0.0 and 1.0. Highly relevant pairs typically score above 0.50 (up to 1.0), while completely irrelevant pairs drop significantly closer to 0.00.\n\n"
        "[bold yellow]Notice the Margin:[/bold yellow]\n"
        "Observe how the Cross-Encoder establishes a much wider relative margin between relevant and irrelevant documents, whereas the Bi-Encoder scores are often clustered close together (e.g., all between 0.65 and 0.85)."
    )
    console.print(
        Panel(
            analysis_text,
            title="[bold yellow]Analysis Guide[/bold yellow]",
            border_style="yellow",
            padding=(1, 2)
        )
    )
    console.print()

def handle_custom_input():
    console.print(Rule("[bold yellow]Setup Custom Scenario[/bold yellow]", style="yellow"))
    console.print()
    console.print("[dim]Enter your own query and a list of candidate documents to see how both models rank them.[/dim]")
    console.print()
    
    query = ""
    while not query.strip():
        query = console.input("[bold cyan]Enter Query: [/bold cyan]")
        if not query.strip():
            console.print("[bold red]Query cannot be empty![/bold red]")
            
    console.print()
    console.print("[bold cyan]Enter Candidate Documents (enter an empty line when finished):[/bold cyan]")
    docs = []
    doc_idx = 1
    while True:
        doc = console.input(f"  [dim]Doc #{doc_idx}:[/dim] ")
        if not doc.strip():
            if len(docs) < 2:
                console.print("[bold red]Please enter at least 2 documents to compare ranking.[/bold red]")
                continue
            break
        docs.append(doc.strip())
        doc_idx += 1
        
    console.print()
    run_custom_scenario(query, docs)

def main():
    parser = argparse.ArgumentParser(description="Cross-Encoder vs Bi-Encoder Ranking Prototype")
    parser.add_argument(
        "-s", "--scenario", 
        choices=["1", "2", "3", "all"], 
        help="Run a specific scenario (1, 2, 3) or 'all' scenarios"
    )
    parser.add_argument(
        "-q", "--query", 
        help="A custom query string (requires --docs)"
    )
    parser.add_argument(
        "-d", "--docs", 
        nargs="+", 
        help="A list of custom document strings to rank"
    )
    parser.add_argument(
        "-i", "--interactive", 
        action="store_true", 
        help="Force interactive mode"
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold yellow]Cross-Encoder vs Bi-Encoder Prototype[/bold yellow]\n"
            "[dim]Demonstrating the limitations of bi-encoders and the precision of cross-encoders.[/dim]\n"
            "[dim]Features: Word Sense Disambiguation, Logic Traps, Asymmetric Directional Search[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    if args.query and args.docs:
        run_custom_scenario(args.query, args.docs)
        return
    elif args.query or args.docs:
        console.print("[bold red]Error:[/bold red] Both --query and --docs must be provided together.")
        parser.print_help()
        sys.exit(1)

    if args.scenario and not args.interactive:
        if args.scenario == "all":
            for sid, sdata in SCENARIOS.items():
                run_scenario(sid, sdata)
        else:
            run_scenario(args.scenario, SCENARIOS[args.scenario])
        return

    if not args.interactive and not args.scenario and not args.query:
        if not sys.stdin.isatty():
            console.print("[dim]Non-interactive terminal detected. Defaulting to running all scenarios...[/dim]\n")
            for sid, sdata in SCENARIOS.items():
                run_scenario(sid, sdata)
            return

    try:
        while True:
            console.print("[bold yellow]Please select a demonstration scenario:[/bold yellow]")
            console.print("  [bold cyan]1[/bold cyan]) Word Sense Ambiguity (e.g. 'apple computer' - Fruit vs Tech)")
            console.print("  [bold cyan]2[/bold cyan]) Logical Logic Trap (e.g. 'Does aspirin treat headaches?' - Causal/Negation)")
            console.print("  [bold cyan]3[/bold cyan]) Asymmetric/Directional Search (e.g. 'flight from Boston to New York')")
            console.print("  [bold cyan]4[/bold cyan]) Run All Scenarios")
            console.print("  [bold cyan]5[/bold cyan]) Custom Query & Documents")
            console.print("  [bold cyan]q[/bold cyan]) Quit")
            console.print()

            choice = console.input("[bold green]Choice: [/bold green]").strip().lower()
            console.print()

            if choice == "q":
                console.print("[bold green]Thank you for using the Cross-Encoder vs Bi-Encoder Prototype![/bold green]")
                break
            elif choice in ["1", "2", "3"]:
                run_scenario(choice, SCENARIOS[choice])
            elif choice == "4":
                for sid, sdata in SCENARIOS.items():
                    run_scenario(sid, sdata)
            elif choice == "5":
                handle_custom_input()
            else:
                console.print("[bold red]Invalid option. Please try again.[/bold red]\n")
    except (KeyboardInterrupt, EOFError):
        console.print()
        console.print("[bold yellow]Exiting due to interrupt or non-interactive environment.[/bold yellow]")
        console.print("[bold green]Thank you for using the Cross-Encoder vs Bi-Encoder Prototype![/bold green]")

if __name__ == "__main__":
    main()
