import os
import json
import uuid
import re
import time
from typing import List, Dict, Tuple
from google import genai
from google.genai import types
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from pypdf import PdfReader
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text
import textwrap

# Initialize Console for rich output
console = Console()


class GoogleGenAIEmbeddingFunction(EmbeddingFunction):
    """Custom embedding function using the google-genai SDK for ChromaDB.

    This class adapts the Gemini embedding models for use with ChromaDB's
    EmbeddingFunction interface, handling batching to improve performance.
    """

    def __init__(self, client: genai.Client, model_name: str):
        """Initializes the embedding function with a Gemini client and model.

        client: An instance of google.genai.Client.
        model_name: The string ID of the embedding model (e.g., models/gemini-embedding-2).
        """
        self.client = client
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        """Embeds a list of documents using the Gemini API.

        input: A list of strings to be embedded.
        Returns a list of embedding vectors (list of floats).
        """
        if not input:
            return []

        all_embeddings = []
        for doc in input:
            # The SDK currently doesn't support batching multiple separate documents
            # into one request that returns multiple embeddings. We loop instead.
            response = self.client.models.embed_content(
                model=self.model_name, contents=doc
            )
            # Each response contains a single embedding list in its .embeddings attribute
            all_embeddings.append(response.embeddings[0].values)

        return all_embeddings


class CustomChunker:
    """Provides manual implementations of various text chunking strategies.

    These methods demonstrate the logic behind common RAG preprocessing steps
    without relying on external libraries like LangChain.
    """

    @staticmethod
    def get_sentences(text: str) -> List[str]:
        """Splits text into individual sentences using regular expressions.

        Uses a lookbehind/lookahead pattern to split on punctuation followed
        by an uppercase letter, which is a common sentence boundary heuristic.
        """
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def fixed_size_chunking(
        text: str, chunk_size: int = 512, overlap: int = 50
    ) -> List[str]:
        """Splits text into chunks of a fixed word count with optional overlap.

        text: The source text to split.
        chunk_size: Number of words per chunk.
        overlap: Number of words to overlap between adjacent chunks.
        Returns a list of text chunks.
        """
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            # Slice the word list and join back into a string
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)
            # Slide the window forward by chunk_size minus overlap
            i += chunk_size - overlap
        return chunks

    @staticmethod
    def semantic_chunking(
        text: str, embedding_fn: EmbeddingFunction, threshold: float = 0.85
    ) -> List[str]:
        """Groups sentences based on their semantic similarity.

        Calculates the cosine similarity between the current sentence and the
        previous one. Starts a new chunk when similarity falls below the threshold.
        """
        sentences = CustomChunker.get_sentences(text)
        if not sentences:
            return []

        # Embed all sentences in one batch call to the API
        sentence_embeddings = embedding_fn(sentences)

        if len(sentence_embeddings) != len(sentences):
            console.print(
                f"[red]Warning: Embedding count ({len(sentence_embeddings)}) mismatch.[/red]"
            )
            min_len = min(len(sentence_embeddings), len(sentences))
            sentences = sentences[:min_len]
            sentence_embeddings = sentence_embeddings[:min_len]

        def cosine_sim(vec1, vec2):
            """Calculates dot product similarity (assuming vectors are normalized)."""
            return sum(a * b for a, b in zip(vec1, vec2))

        chunks = []
        current_chunk_sentences = [sentences[0]]
        last_sentence_embedding = sentence_embeddings[0]

        for i in range(1, len(sentences)):
            sim = cosine_sim(last_sentence_embedding, sentence_embeddings[i])
            if sim >= threshold:
                # Same semantic context, add to current chunk
                current_chunk_sentences.append(sentences[i])
                last_sentence_embedding = sentence_embeddings[i]
            else:
                # Semantic break detected, finalize current chunk and start new one
                chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentences[i]]
                last_sentence_embedding = sentence_embeddings[i]

        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences))

        return chunks

    @staticmethod
    def parent_child_chunking(
        text: str, parent_size: int = 2000, child_size: int = 400
    ) -> Tuple[List[Dict], List[Dict]]:
        """Generates large parent chunks and smaller child chunks for dual-indexing.

        This strategy helps retrieve precise sections (children) while providing
        the LLM with broader context (parents).
        Returns (child_docs, parent_docs).
        """
        # Create large parent documents first
        parent_texts = CustomChunker.fixed_size_chunking(
            text, chunk_size=parent_size, overlap=100
        )

        parents = []
        children = []

        for p_text in parent_texts:
            p_id = str(uuid.uuid4())
            parents.append({"id": p_id, "text": p_text})

            # Create multiple smaller children for each parent
            c_texts = CustomChunker.fixed_size_chunking(
                p_text, chunk_size=child_size, overlap=50
            )
            for c_text in c_texts:
                c_id = str(uuid.uuid4())
                children.append({"id": c_id, "text": c_text, "parent_id": p_id})

        return children, parents


class ChunkingEvaluator:
    """Orchestrates the evaluation of different chunking strategies.

    Manages data loading, indexing in ChromaDB, and running precision tests
    using Gemini as the evaluation judge.
    """

    def __init__(self, pdf_path: str, eval_queries_path: str):
        """Loads the document and evaluation dataset."""
        self.pdf_path = pdf_path
        self.eval_queries = self._load_queries(eval_queries_path)
        self.text = self._extract_text(pdf_path)

        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.embedding_model = "models/gemini-embedding-2"
        self.eval_model = "gemini-2.5-flash"

        # In-memory ChromaDB client for temporary storage during comparison
        self.chroma_client = chromadb.Client()
        self.embedding_fn = GoogleGenAIEmbeddingFunction(
            client=self.client, model_name=self.embedding_model
        )

    def _load_queries(self, path: str) -> List[Dict]:
        """Loads evaluation queries from a JSON file.

        Limits scope to the first 5 queries for faster prototype demonstration.
        """
        with open(path, "r") as f:
            queries = json.load(f)
            return queries[:5]

    def _extract_text(self, pdf_path: str) -> str:
        """Reads text from a PDF file.

        Limits processing to the first 5 pages to keep the prototype fast.
        """
        reader = PdfReader(pdf_path)
        text = ""
        max_pages = min(5, len(reader.pages))
        console.print(
            f"[dim]Extracting text from first {max_pages} pages for fast execution...[/dim]"
        )
        for page in reader.pages[:max_pages]:
            text += page.extract_text() + "\n\n"
        return text

    def evaluate_fixed_size(self) -> Dict:
        """Evaluates the Fixed-Size chunking strategy."""
        console.print(
            "\n[bold cyan]-- Preparing Strategy: Fixed-Size (512) --------------------------------------[/bold cyan]"
        )
        chunks = CustomChunker.fixed_size_chunking(
            self.text, chunk_size=512, overlap=50
        )

        collection = self.chroma_client.create_collection(
            name="fixed_size_" + str(uuid.uuid4())[:8],
            embedding_function=self.embedding_fn,
        )

        ids = [str(uuid.uuid4()) for _ in chunks]

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Indexing Fixed-Size chunks...", total=len(chunks)
            )
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                collection.add(
                    documents=chunks[i : i + batch_size], ids=ids[i : i + batch_size]
                )
                progress.update(task, advance=len(chunks[i : i + batch_size]))

        return self._run_evaluation(collection, "Fixed-Size (512)")

    def evaluate_semantic(self) -> Dict:
        """Evaluates the Semantic chunking strategy."""
        console.print(
            "\n[bold magenta]-- Preparing Strategy: Semantic --------------------------------------[/bold magenta]"
        )
        chunks = CustomChunker.semantic_chunking(self.text, self.embedding_fn)

        collection = self.chroma_client.create_collection(
            name="semantic_" + str(uuid.uuid4())[:8],
            embedding_function=self.embedding_fn,
        )

        ids = [str(uuid.uuid4()) for _ in chunks]

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Indexing Semantic chunks...", total=len(chunks)
            )
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                collection.add(
                    documents=chunks[i : i + batch_size], ids=ids[i : i + batch_size]
                )
                progress.update(task, advance=len(chunks[i : i + batch_size]))

        return self._run_evaluation(collection, "Semantic")

    def evaluate_parent_child(self) -> Dict:
        """Evaluates the Parent-Child chunking strategy."""
        console.print(
            "\n[bold cyan]-- Preparing Strategy: Parent-Child --------------------------------------[/bold cyan]"
        )
        children, parents = CustomChunker.parent_child_chunking(self.text)

        parent_store = {p["id"]: p["text"] for p in parents}

        collection = self.chroma_client.create_collection(
            name="parent_child_" + str(uuid.uuid4())[:8],
            embedding_function=self.embedding_fn,
        )

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Indexing Child chunks...", total=len(children)
            )
            batch_size = 100
            for i in range(0, len(children), batch_size):
                batch = children[i : i + batch_size]
                collection.add(
                    documents=[c["text"] for c in batch],
                    metadatas=[{"parent_id": c["parent_id"]} for c in batch],
                    ids=[c["id"] for c in batch],
                )
                progress.update(task, advance=len(batch))

        return self._run_evaluation(
            collection, "Parent-Child", parent_store=parent_store
        )

    def _run_evaluation(
        self, collection, strategy_name: str, parent_store: dict = None
    ) -> Dict:
        """Retrieves context for each query and checks relevance with an LLM.

        Iterates through the evaluation queries, performs vector search,
        and uses Gemini to determine if the retrieved context is correct.
        """
        hits = 0
        total = len(self.eval_queries)

        with Progress() as progress:
            task = progress.add_task(
                f"[cyan]Evaluating {strategy_name}...", total=total
            )

            for item in self.eval_queries:
                query = item["question"]
                expected_answer = item["answer"]

                # Retrieve top 5 matches
                results = collection.query(query_texts=[query], n_results=5)

                if parent_store:
                    # Map retrieved children back to their larger parent context
                    parent_ids = [meta["parent_id"] for meta in results["metadatas"][0]]
                    unique_parent_ids = list(dict.fromkeys(parent_ids))
                    retrieved_texts = [parent_store[pid] for pid in unique_parent_ids]
                else:
                    retrieved_texts = results["documents"][0]

                context = "\n---\n".join(retrieved_texts)

                if self._is_relevant(query, expected_answer, context):
                    hits += 1

                progress.update(task, advance=1)

        precision = (hits / total) * 100
        return {
            "strategy": strategy_name,
            "hits": hits,
            "total": total,
            "precision": precision,
        }

    def _is_relevant(self, query: str, expected_answer: str, context: str) -> bool:
        """Determines if the context contains the answer using Gemini.

        Styles the LLM input and output using rich Panels for a chat-like aesthetic.
        Includes basic retry logic for robustness.
        """
        prompt = f"""
        You are an evaluator for a RAG system.
        Query: {query}
        Expected Answer: {expected_answer}
        
        Retrieved Context:
        {context}
        
        Based ONLY on the retrieved context, can the query be accurately answered?
        The context should contain the key information mentioned in the expected answer.
        
        Respond with ONLY 'YES' or 'NO'.
        """

        # Model Input display
        input_elements = []
        wrapped_prompt = textwrap.fill(
            prompt.strip(), width=82, subsequent_indent="     "
        )
        input_elements.append(
            Text.assemble(("USER: ", "bold blue"), (wrapped_prompt, "blue"))
        )

        console.print(
            Panel(
                Group(*input_elements),
                title="[bold bright_black]Model Input[/bold bright_black]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )

        def _call_model():
            response = self.client.models.generate_content(
                model=self.eval_model, contents=prompt
            )
            result = response.text.strip().upper()

            # Model Response display
            wrapped_response = textwrap.fill(
                result, width=82, subsequent_indent="           "
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
            return "YES" in result

        try:
            return _call_model()
        except Exception:
            time.sleep(2)  # Simple backoff on error
            try:
                return _call_model()
            except Exception:
                return False


from rich.rule import Rule


def print_results(results: List[Dict]):
    """Displays a summary table of the comparison results and the final verdict."""
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    table = Table(title="Results", show_lines=True)
    table.add_column("Strategy", style="bold cyan")
    table.add_column("Hits", justify="center", style="magenta")
    table.add_column("Total", justify="center", style="dim")
    table.add_column("Precision (%)", justify="center", style="green")

    for res in results:
        table.add_row(
            res["strategy"],
            str(res["hits"]),
            str(res["total"]),
            f"{res['precision']:.2f}%",
        )

    console.print(table)

    best = max(results, key=lambda x: x["precision"])
    console.print(
        Panel(
            f"[bold green]Verdict:[/bold green] The [bold cyan]{best['strategy']}[/bold cyan] strategy "
            f"performed best with [bold green]{best['precision']:.2f}%[/bold green] precision.",
            title="[bold yellow]Conclusion[/bold yellow]",
            border_style="yellow",
        )
    )


if __name__ == "__main__":
    # Ensure dependencies and keys are present
    if "GEMINI_API_KEY" not in os.environ:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set."
        )
        raise SystemExit(1)

    console.print(
        Panel.fit(
            "[bold yellow]RAG Chunking Strategy Comparison[/bold yellow]\n"
            "[dim]Evaluates Fixed-Size, Semantic, and Parent-Child chunking against ground truth queries.[/dim]\n"
            "[dim]3 strategies × 5 queries[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    evaluator = ChunkingEvaluator("technical_doc.pdf", "eval_queries.json")

    results = []
    # Run evaluation sequentially for each strategy
    results.append(evaluator.evaluate_fixed_size())
    results.append(evaluator.evaluate_semantic())
    results.append(evaluator.evaluate_parent_child())

    print_results(results)
