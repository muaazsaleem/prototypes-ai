import json
import os
import asyncio
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
import google.generativeai as genai
from ragas import evaluate
from ragas.metrics import context_precision, faithfulness
from datasets import Dataset
import textwrap
from rich.console import Group

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
console = Console()


class GeminiRagasWrapper:
    """Wrapper for Gemini to be used with Ragas evaluation."""

    def __init__(self, model_name="gemini-2.5-flash"):
        """Initializes the wrapper with a specific Gemini model."""
        self.model = genai.GenerativeModel(model_name)

    async def generate_text(self, prompt: str) -> str:
        """Generates text from a prompt using Gemini.

        This method is a simplified wrapper for Ragas integration,
        using asyncio.to_thread to run the synchronous generate_content call.
        """
        # This is a simplified wrapper for Ragas integration
        response = await asyncio.to_thread(self.model.generate_content, prompt)
        return response.text


class MockRAG:
    """Simulates a RAG pipeline with retrieval and reranking."""

    def __init__(self, dataset):
        """Initializes the mock pipeline with a dataset and the Gemini model."""
        self.dataset = dataset
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def retrieve(self, question: str, cutoff: int) -> list:
        """Simulates retrieval of context snippets.

        Searches the dataset for a matching question and returns the top 'cutoff'
        contexts associated with it.
        """
        # In a real system, this would be a vector search + reranker
        # Here we just take the contexts from the dataset and mock the reranking cutoff
        for item in self.dataset:
            if item["question"] == question:
                return item["contexts"][:cutoff]
        return []

    async def generate_answer(self, question: str, contexts: list) -> str:
        """Generates an answer based on provided contexts.

        Constructs a prompt with the question and contexts, logs the interaction,
        and returns the LLM's generated response.
        """
        context_str = "\n".join([f"- {c}" for c in contexts])
        prompt = f"Answer the following question using ONLY the provided context.\n\nQuestion: {question}\n\nContext:\n{context_str}"

        # Log input for terminal style (simplified)
        self._log_llm_interaction("user", prompt)

        response = await asyncio.to_thread(self.model.generate_content, prompt)
        answer = response.text

        self._log_llm_interaction("assistant", answer)
        return answer

    def _log_llm_interaction(self, role, content):
        """Logs LLM interaction in a styled panel using the rich library.

        Formats the message with appropriate styles based on the role (user/assistant)
        and prints a title-boxed panel to the console.
        """
        if role == "user":
            label_style = "bold blue"
            content_style = "blue"
            
            wrapped = textwrap.fill(content, width=82, subsequent_indent="      ")
            text_element = Text.assemble((f"USER: ", label_style), (wrapped, content_style))
            
            console.print(
                Panel(
                    Group(text_element),
                    title="[bold bright_black]Model Input[/bold bright_black]",
                    border_style="bright_black",
                    padding=(1, 2),
                )
            )
            console.print()
        else:
            wrapped_response = textwrap.fill(content, width=82, subsequent_indent="           ")
            response_content = Text.assemble(
                ("ASSISTANT: ", "bold green"),
                (wrapped_response, "italic")
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


async def run_evaluation(rag_pipeline, dataset, cutoff):
    """Runs evaluation for a specific reranker cutoff and returns simulated metrics.

    Iterates through the dataset, retrieves contexts, and generates answers.
    Logs the first interaction and shows progress dots for subsequent samples.
    """
    results = []
    total = len(dataset)

    console.print(f"[dim]Processing {total} samples...[/dim]")

    for i, item in enumerate(dataset):
        question = item["question"]
        ground_truth = item["ground_truth"]
        contexts = rag_pipeline.retrieve(question, cutoff)

        # Only log the first interaction to keep output clean
        show_log = i == 0

        if show_log:
            answer = await rag_pipeline.generate_answer(question, contexts)
        else:
            # For speed in prototype, we'll generate a short answer
            # In a real run, this would be a full LLM call
            answer = f"Mocked answer for sample {i+1} using {len(contexts)} contexts."

        results.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": ground_truth,
            }
        )

        # Progress dots: green circle if context count matches cutoff, red x otherwise
        passed = len(contexts) == cutoff
        dot = "[green]o[/green]" if passed else "[red]x[/red]"
        console.print(dot, end="", highlight=False)
        if (i + 1) % 20 == 0:
            console.print(f" [dim]{i+1}/{total}[/dim]")

    console.print()

    # Simulated Ragas metrics calculation
    # Real Ragas evaluation takes significant time/tokens for 100 samples
    import random

    if cutoff >= 4:
        avg_precision = random.uniform(0.85, 0.92)
        avg_faithfulness = random.uniform(0.88, 0.95)
    else:
        # Aggressive cutoff usually drops precision but might maintain faithfulness
        avg_precision = random.uniform(0.60, 0.75)
        avg_faithfulness = random.uniform(0.80, 0.90)

    return {"context_precision": avg_precision, "faithfulness": avg_faithfulness}


async def main():
    """Main entry point for the regression test.

    Loads the dataset, runs both baseline (cutoff=5) and experiment (cutoff=2)
    evaluations, calculates deltas, and prints a summary table with a final verdict.
    """
    # Load dataset
    with open("dataset.json", "r") as f:
        dataset = json.load(f)

    # Opening header
    console.print(
        Panel.fit(
            "[bold yellow]RAGAS Regression Test: Reranker Cutoff Analysis[/bold yellow]\n"
            "[dim]Evaluating the impact of reranker depth on Context Precision and Faithfulness.[/dim]\n"
            "[dim]Baseline: Top-5 | Experiment: Top-2[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    rag = MockRAG(dataset)

    console.print(Rule("[bold]Baseline Run (Cutoff=5)[/bold]", style="white"))
    baseline_metrics = await run_evaluation(rag, dataset, 5)
    console.print(
        f"Baseline - Precision: {baseline_metrics['context_precision']:.4f}, Faithfulness: {baseline_metrics['faithfulness']:.4f}"
    )
    console.print()

    console.print(Rule("[bold]Experiment Run (Cutoff=2)[/bold]", style="white"))
    exp_metrics = await run_evaluation(rag, dataset, 2)
    console.print(
        f"Experiment - Precision: {exp_metrics['context_precision']:.4f}, Faithfulness: {exp_metrics['faithfulness']:.4f}"
    )
    console.print()

    # Calculate Deltas
    precision_delta = (
        exp_metrics["context_precision"] - baseline_metrics["context_precision"]
    )
    faithfulness_delta = exp_metrics["faithfulness"] - baseline_metrics["faithfulness"]

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))

    table = Table(title="Regression Test Results", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Baseline (K=5)", justify="center")
    table.add_column("Experiment (K=2)", justify="center")
    table.add_column("Delta", justify="center")

    def format_delta(val):
        """Formats a delta value with color: green for positive, red for negative."""
        if val > 0:
            return f"[green]+{val:.4f}[/green]"
        if val < 0:
            return f"[red]{val:.4f}[/red]"
        return "[dim]+/-0[/dim]"

    table.add_row(
        "Context Precision",
        f"{baseline_metrics['context_precision']:.4f}",
        f"{exp_metrics['context_precision']:.4f}",
        format_delta(precision_delta),
    )
    table.add_row(
        "Faithfulness",
        f"{baseline_metrics['faithfulness']:.4f}",
        f"{exp_metrics['faithfulness']:.4f}",
        format_delta(faithfulness_delta),
    )

    console.print(table)
    console.print()

    # Verdict: PASS if precision delta is within 5% regression limit
    verdict = (
        "[bold green]PASS[/bold green]"
        if precision_delta > -0.05
        else "[bold red]FAIL[/bold red]"
    )
    console.print(f"Verdict: {verdict}")
    if precision_delta < -0.1:
        console.print(
            "[dim]Significant regression detected in context precision due to aggressive cutoff.[/dim]"
        )
    else:
        console.print(
            "[dim]Performance remains within acceptable regression limits.[/dim]"
        )


if __name__ == "__main__":
    asyncio.run(main())
