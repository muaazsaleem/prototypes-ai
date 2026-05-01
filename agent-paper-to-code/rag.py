from typing import Dict, List

import chromadb
from google import genai

from config import CHROMA_DB_PATH, EMBEDDING_MODEL, TOP_K_CHUNKS

COLLECTION_NAME = "paper_chunks"


class RAGStore:
    def __init__(self, client: genai.Client):
        """Initialise the vector store, creating the ChromaDB collection if it doesn't exist.

        Uses cosine distance as the similarity metric so that embedding magnitude
        doesn't affect ranking (Gemini embeddings are not unit-normalised).
        """
        self.client = client
        self.chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = self.chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine"
            },  # cosine is better than L2 for text embeddings
        )

    def embed(self, text: str) -> List[float]:
        """Return a float vector for the given text using the Gemini embedding model.

        result.embeddings is always a list even for a single input;
        index 0 gives the ContentEmbedding for the one string we passed.
        """
        result = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
        return list(result.embeddings[0].values)

    def index_chunks(self, chunks: List[Dict]) -> None:
        """Embed every chunk and upsert it into ChromaDB, mutating the collection.

        Processes in batches of 10 to stay within the Gemini embedding API's
        recommended request size and avoid hitting rate limits on large papers.
        """
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            embeddings = [self.embed(t) for t in texts]
            self.collection.add(ids=ids, documents=texts, embeddings=embeddings)

    def retrieve(self, query: str, top_k: int = TOP_K_CHUNKS) -> List[str]:
        """Return the top-k chunk texts most similar to the query.

        Clamps n_results to the actual collection size because ChromaDB raises
        if you request more results than documents currently stored.
        Returns a flat list of strings (not dicts), ready to inject into a prompt.
        """
        query_embedding = self.embed(query)
        n = min(
            top_k, self.collection.count()
        )  # guard against empty or small collections
        if n == 0:
            return []
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
        )
        return results["documents"][
            0
        ]  # outer list is per-query; [0] = our single query

    def clear(self) -> None:
        """Delete and recreate the collection, removing all previously indexed chunks.

        Delete can fail if the collection doesn't exist yet (first run), so the
        exception is swallowed before recreating.
        """
        try:
            self.chroma.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        """Return the number of chunks currently stored in the collection."""
        return self.collection.count()
