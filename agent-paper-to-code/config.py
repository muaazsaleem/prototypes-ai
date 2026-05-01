import os

# Gemini model identifiers
GEMINI_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"

# PDF chunking: how large each text chunk is and how much consecutive chunks overlap
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

# Number of chunks to pull back from the vector store per query
TOP_K_CHUNKS = 5

# Semantic cache: queries whose embeddings are this similar are treated as duplicates
CACHE_SIMILARITY_THRESHOLD = 0.90

# Persistence paths (created automatically on first run)
CHROMA_DB_PATH = "./chroma_db"
SEMANTIC_CACHE_PATH = "./semantic_cache.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Optional — avoids rate limits and unlocks GitHub code search
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
