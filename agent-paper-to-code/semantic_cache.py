import json
from typing import List, Optional, Tuple

import numpy as np

from config import CACHE_SIMILARITY_THRESHOLD, SEMANTIC_CACHE_PATH


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Return cosine similarity in [-1, 1] between two embedding vectors.

    Returns 0.0 for zero-magnitude vectors to avoid division by zero.
    Higher is more similar; identical vectors return 1.0.
    """
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class SemanticCache:
    """
    Persists (embedding, query, result) triples to disk.
    On lookup, finds the most similar past query by cosine distance.
    If similarity >= threshold, the cached result is returned instead of
    re-running the agent — avoiding redundant LLM calls for repeated runs.
    """

    def __init__(self, threshold: float = CACHE_SIMILARITY_THRESHOLD):
        """Load the cache from disk, or start empty if the file doesn't exist yet."""
        self.threshold = threshold
        self.entries: List[dict] = []
        self._load()

    def _load(self) -> None:
        """Populate self.entries from the JSON file on disk, or initialise to empty list."""
        try:
            with open(SEMANTIC_CACHE_PATH) as f:
                self.entries = json.load(f)
        except FileNotFoundError:
            self.entries = []

    def _save(self) -> None:
        """Persist the current entries list to disk, overwriting the previous file."""
        with open(SEMANTIC_CACHE_PATH, "w") as f:
            json.dump(self.entries, f)

    def get(self, embedding: List[float]) -> Optional[Tuple[str, str]]:
        """Return (original_query, cached_result) if a sufficiently similar entry exists.

        Scans all entries linearly; acceptable because cache size stays small
        (one entry per distinct paper/query pair). Returns None on a miss.
        """
        for entry in self.entries:
            if cosine_similarity(embedding, entry["embedding"]) >= self.threshold:
                return entry["query"], entry["result"]
        return None

    def set(self, embedding: List[float], query: str, result: str) -> None:
        """Append a new entry and immediately flush to disk so nothing is lost on crash."""
        self.entries.append({"embedding": embedding, "query": query, "result": result})
        self._save()

    def size(self) -> int:
        """Return the number of cached entries."""
        return len(self.entries)
