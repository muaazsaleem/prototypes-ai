import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import google.generativeai as genai
from sklearn.metrics.pairwise import cosine_similarity
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from tqdm import tqdm
import textwrap

# Setup
console = Console()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])


def get_model():
    """Returns the Gemini 2.5 Flash model instance."""
    return genai.GenerativeModel("gemini-2.5-flash")


def get_embeddings(texts):
    """Batch computes embeddings for a list of strings using Gemini."""
    result = genai.embed_content(
        model="models/gemini-embedding-2", content=texts, task_type="retrieval_document"
    )
    return np.array(result["embedding"])


def generate_queries(count=500):
    """Generates a diverse set of synthetic queries for testing.

    Returns a list of query objects containing the text, type, and relationship IDs.
    Caches results to 'queries.json' to avoid redundant API calls.
    """
    if os.path.exists("queries.json"):
        with open("queries.json", "r") as f:
            return json.load(f)

    console.print("[bold cyan]Generating 500 diverse queries...[/bold cyan]")
    model = get_model()

    topics = [
        "Python Programming",
        "World History",
        "Cooking Recipes",
        "Space Exploration",
        "Financial Planning",
        "Health & Fitness",
        "Movies & Cinema",
        "Geography",
        "Quantum Physics",
        "Gardening",
    ]

    all_queries = []

    # Generate initial seed queries for each predefined topic
    for topic in tqdm(topics, desc="Generating Seeds"):
        prompt = f"Generate 20 diverse, realistic user queries about {topic}. Return only a JSON list of strings."
        response = model.generate_content(prompt)
        try:
            # Strip markdown formatting and parse JSON from the LLM response
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            queries = json.loads(text)
            for q in queries[:20]:
                all_queries.append({"query": q, "type": "seed", "id": len(all_queries)})
        except:
            continue

    # Use first 150 seeds to create paraphrases (expected hits) and near-misses (expected misses)
    seeds = [q for q in all_queries if q["type"] == "seed"][:150]

    for i in tqdm(range(0, len(seeds), 10), desc="Generating Variations"):
        batch = seeds[i : i + 10]
        batch_texts = [b["query"] for b in batch]

        # Generate paraphrases that ask the same thing in different words
        prompt = f"For each of these queries, write one semantic paraphrase that asks the same thing in different words:\n{json.dumps(batch_texts)}\nReturn a JSON list of strings."
        response = model.generate_content(prompt)
        try:
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            paraphrases = json.loads(text)
            for j, p in enumerate(paraphrases):
                all_queries.append(
                    {"query": p, "type": "paraphrase", "parent_id": batch[j]["id"]}
                )
        except:
            pass

        # Generate near-misses that share topics but have different intents
        prompt = f"For each of these queries, write one query that is on the SAME SPECIFIC TOPIC but asks for something DIFFERENT (different intent):\n{json.dumps(batch_texts)}\nReturn a JSON list of strings."
        response = model.generate_content(prompt)
        try:
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            near_misses = json.loads(text)
            for j, n in enumerate(near_misses):
                all_queries.append(
                    {"query": n, "type": "near_miss", "parent_id": batch[j]["id"]}
                )
        except:
            pass

    # Ensure the dataset reaches the requested count with random seed queries
    if len(all_queries) < 500:
        needed = 500 - len(all_queries)
        prompt = f"Generate {needed} random realistic user queries. JSON list."
        response = model.generate_content(prompt)
        try:
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            extra = json.loads(text)
            for e in extra:
                all_queries.append({"query": e, "type": "seed", "id": len(all_queries)})
        except:
            pass

    with open("queries.json", "w") as f:
        json.dump(all_queries[:500], f)

    return all_queries[:500]


def show_demo_interaction():
    """Shows a single styled LLM interaction for demonstration purposes."""
    model = get_model()
    query = "What is semantic caching?"

    # Model Input Display
    messages = [{"role": "user", "content": query}]
    input_elements = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        label_style = "bold blue"
        content_style = "blue"
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    response = model.generate_content(query)
    response_text = response.text

    # Model Output Display
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


def run_calibration():
    """Performs threshold sweep to find the optimal semantic cache similarity setting.

    Calculates hit rate and precision across a range of cosine similarity thresholds.
    Outputs a summary table and saves a calibration curve plot to disk.
    """
    show_demo_interaction()

    console.print(
        Panel.fit(
            "[bold yellow]Semantic Cache Threshold Tuning[/bold yellow]\n"
            "[dim]Calibrating Hit Rate vs. Accuracy across similarity thresholds.[/dim]\n"
            "[dim]Dataset: 500 queries (Seeds, Paraphrases, Traps)[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    queries_data = generate_queries(500)
    texts = [q["query"] for q in queries_data]

    console.print("[bold cyan]Computing embeddings...[/bold cyan]")
    embeddings = get_embeddings(texts)

    thresholds = np.arange(0.70, 0.96, 0.02)
    results = []

    console.print(Rule("[bold]Sweep Execution[/bold]", style="white"))

    for t in thresholds:
        hits = 0
        correct_hits = 0
        total = 0

        # Simulate a simple cache with a first-in-first-out population strategy
        cache_embeddings = []
        cache_metadata = []

        for i in range(len(queries_data)):
            q = queries_data[i]
            emb = embeddings[i].reshape(1, -1)

            is_hit = False
            if cache_embeddings:
                # Compare current query against all previously cached entries
                similarities = cosine_similarity(emb, np.array(cache_embeddings))[0]
                max_sim = np.max(similarities)
                if max_sim >= t:
                    is_hit = True
                    hit_idx = np.argmax(similarities)
                    hits += 1

                    # Verify if the hit shares the same underlying intent (parent ID)
                    current_parent = q.get("parent_id", q.get("id"))
                    cached_parent = cache_metadata[hit_idx].get(
                        "parent_id", cache_metadata[hit_idx].get("id")
                    )

                    if current_parent == cached_parent:
                        correct_hits += 1

            if not is_hit:
                # Populate cache only on misses to mimic real-world behavior
                cache_embeddings.append(embeddings[i])
                cache_metadata.append(q)

            total += 1

        hit_rate = (hits / total) * 100
        accuracy = (correct_hits / hits * 100) if hits > 0 else 100.0

        results.append({"threshold": t, "hit_rate": hit_rate, "accuracy": accuracy})

        # Display progress indicator with color-coded accuracy status
        dot = (
            "[green]o[/green]"
            if accuracy > 90
            else "[yellow]o[/yellow]" if accuracy > 70 else "[red]o[/red]"
        )
        console.print(
            f"  T={t:.2f}: {dot} HR:{hit_rate:4.1f}% Acc:{accuracy:4.1f}%",
            end="   ",
            highlight=False,
        )
        if len(results) % 3 == 0:
            console.print()

    console.print("\n")
    console.print(
        Rule("[bold yellow]Final Calibration Artifact[/bold yellow]", style="yellow")
    )

    # Render results table with performance verdicts based on hit rate and precision
    table = Table(title="Threshold Sensitivity Analysis", show_lines=True)
    table.add_column("Threshold", justify="center", style="bold")
    table.add_column("Hit Rate", justify="center", style="cyan")
    table.add_column("Hit Accuracy (Precision)", justify="center", style="magenta")
    table.add_column("Verdict", justify="center")

    for r in results:
        verdict = (
            "[bold green]Optimal[/bold green]"
            if r["accuracy"] > 95 and r["hit_rate"] > 10
            else "[dim]Suboptimal[/dim]"
        )
        if r["accuracy"] < 80:
            verdict = "[bold red]Risky[/bold red]"

        table.add_row(
            f"{r['threshold']:.2f}",
            f"{r['hit_rate']:.1f}%",
            f"{r['accuracy']:.1f}%",
            verdict,
        )

    console.print(table)

    # Generate trade-off visualization for reporting
    plt.figure(figsize=(10, 6))
    plt.plot(
        [r["threshold"] for r in results],
        [r["hit_rate"] for r in results],
        label="Hit Rate (%)",
        marker="o",
        color="cyan",
    )
    plt.plot(
        [r["threshold"] for r in results],
        [r["accuracy"] for r in results],
        label="Accuracy (%)",
        marker="s",
        color="magenta",
    )
    plt.axvline(x=0.90, color="gray", linestyle="--", label="Common Baseline (0.90)")
    plt.xlabel("Similarity Threshold")
    plt.ylabel("Percentage (%)")
    plt.title("Semantic Cache: Hit Rate vs. Accuracy Tradeoff")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig("calibration_curve.png")
    console.print(
        "\n[bold green]Calibration curve saved to 'calibration_curve.png'[/bold green]"
    )

    # Identify and recommend the highest hit rate threshold that maintains 95%+ precision
    best_t = max(results, key=lambda x: x["hit_rate"] if x["accuracy"] >= 95 else 0)
    console.print(
        f"\n[bold yellow]Recommended Threshold:[/bold yellow] {best_t['threshold']:.2f} (Accuracy: {best_t['accuracy']:.1f}%, Hit Rate: {best_t['hit_rate']:.1f}%)"
    )


if __name__ == "__main__":
    run_calibration()
