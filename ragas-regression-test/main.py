import json
import os
import asyncio
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
import textwrap
from rich.console import Group

# Import SDKs
from google import genai
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

# Import Ragas and LangChain evaluation dependencies
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import ContextPrecision, Faithfulness
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# Silence ChromaDB telemetry
os.environ["CHROMA_TELEMETRY"] = "false"
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# Initialize the generative AI Client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
console = Console()


from tenacity import retry, stop_after_attempt, wait_exponential

class FixedGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
    """Overrides the LangChain embedding class to fix batching issues and add retry logic."""
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(text)

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Custom embedding function for ChromaDB utilizing Google GenAI."""

    def __init__(self):
        """Initializes the fixed LangChain wrapper for Google embeddings."""
        self.embeddings = FixedGoogleEmbeddings(model="models/gemini-embedding-2")

    def __call__(self, input: Documents) -> Embeddings:
        """Embeds a list of strings iteratively to avoid API list-as-single-prompt bugs."""
        return self.embeddings.embed_documents(input)


class RealRAG:
    """A real RAG pipeline utilizing ChromaDB for retrieval."""

    def __init__(self, dataset):
        """Initializes ChromaDB, creates a collection, and embeds all dataset contexts."""
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.create_collection(
            name="rag_docs", embedding_function=GeminiEmbeddingFunction()
        )

        console.print("[dim]Building ChromaDB Knowledge Base...[/dim]")

        # Flatten all contexts to form a unique knowledge base
        unique_contexts = set()
        for item in dataset:
            for ctx in item["contexts"]:
                unique_contexts.add(ctx)

        docs = list(unique_contexts)
        ids = [f"doc_{i}" for i in range(len(docs))]

        # Add to ChromaDB in batches to respect payload size limits
        batch_size = 100
        for i in range(0, len(docs), batch_size):
            self.collection.add(
                documents=docs[i : i + batch_size], ids=ids[i : i + batch_size]
            )
        console.print(
            f"[dim]Embedded and added {len(docs)} unique documents to ChromaDB.[/dim]\n"
        )

    def retrieve(self, question: str, cutoff: int) -> list:
        """Retrieves the top 'cutoff' most relevant documents from ChromaDB."""
        results = self.collection.query(query_texts=[question], n_results=cutoff)
        # return the list of retrieved context strings
        return results["documents"][0] if results["documents"] else []

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _safe_generate(self, prompt: str) -> str:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text

    async def generate_answer(
        self, question: str, contexts: list, log_interaction: bool = False
    ) -> str:
        """Generates an answer based on provided contexts using Google GenAI."""
        context_str = "\n".join([f"- {c}" for c in contexts])
        prompt = f"Answer the following question using ONLY the provided context.\n\nQuestion: {question}\n\nContext:\n{context_str}"

        if log_interaction:
            self._log_llm_interaction("user", prompt)

        answer = await self._safe_generate(prompt)

        if log_interaction:
            self._log_llm_interaction("assistant", answer)
        return answer

    def _log_llm_interaction(self, role, content):
        """Logs LLM interaction in a styled panel using the rich library."""
        if role == "user":
            label_style = "bold blue"
            content_style = "blue"

            wrapped = textwrap.fill(content, width=82, subsequent_indent="      ")
            text_element = Text.assemble(
                (f"USER: ", label_style), (wrapped, content_style)
            )

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
            wrapped_response = textwrap.fill(
                content, width=82, subsequent_indent="           "
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


async def run_evaluation(rag_pipeline, dataset, cutoff):
    """Runs retrieval, generation, and actual Ragas evaluation."""
    results = []
    total = len(dataset)

    console.print(f"[dim]Running Retrieval & Generation for {total} samples...[/dim]")

    for i, item in enumerate(dataset):
        question = item["question"]
        ground_truth = item["ground_truth"]

        # Perform actual vector retrieval
        contexts = rag_pipeline.retrieve(question, cutoff)

        # Only log the very first interaction to keep the console clean
        show_log = i == 0
        answer = await rag_pipeline.generate_answer(
            question, contexts, log_interaction=show_log
        )

        results.append(
            {
                "user_input": question,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": ground_truth,
            }
        )

        # Progress tracking
        console.print("[green]o[/green]", end="", highlight=False)
        if (i + 1) % 20 == 0:
            console.print(f" [dim]{i+1}/{total}[/dim]")

    console.print()
    console.print(
        "[dim]Running actual RAGAS evaluation (this evaluates via LLM and may take a moment)...[/dim]"
    )

    # Convert results into a HuggingFace Dataset, required by Ragas
    ds = Dataset.from_list(results)

    # Initialize evaluator LLM and Embeddings using LangChain wrappers
    eval_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    eval_embeddings = FixedGoogleEmbeddings(model="models/gemini-embedding-2")

    # Run the actual Ragas evaluation
    score = evaluate(
        dataset=ds,
        metrics=[ContextPrecision(), Faithfulness()],
        llm=eval_llm,
        embeddings=eval_embeddings,
        show_progress=False,
    )

    # The score object is an EvaluationResult. We can convert to pandas to extract scalar means
    df = score.to_pandas()
    return {
        "context_precision": df["context_precision"].mean() if "context_precision" in df else 0.0,
        "faithfulness": df["faithfulness"].mean() if "faithfulness" in df else 0.0,
    }


async def main():
    """Main entry point for the real RAG application regression test."""

    # Load the 100-sample dataset
    with open("dataset.json", "r") as f:
        dataset = json.load(f)

    # Opening header
    console.print(
        Panel.fit(
            "[bold yellow]RAGAS Regression Test: Real Application[/bold yellow]\n"
            "[dim]Evaluating actual ChromaDB retrieval and Gemini 2.5 Flash generation using genuine RAGAS metrics.[/dim]\n"
            "[dim]Baseline: Top-5 | Experiment: Top-2[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Initialize the real RAG pipeline (this builds the Vector DB)
    rag = RealRAG(dataset)

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
