# Paper-to-Code Agent

An AI agent that reads an academic paper (PDF), retrieves relevant sections via RAG, searches GitHub for reference implementations using parallel tool calls, and generates runnable Python code for the paper's core method.

## Concepts demonstrated

| Concept | File |
|---|---|
| PDF ingestion & chunking | `pdf_processor.py` |
| RAG — Gemini embeddings + ChromaDB | `rag.py` |
| Semantic caching (cosine similarity) | `semantic_cache.py` |
| Tool / function definitions | `tools.py` |
| Agentic loop + parallel tool calls | `agent.py` |
| RAGAS-inspired evaluation (LLM-as-judge) | `evaluator.py` |
| Orchestration + Rich terminal output | `main.py` |

## Setup

```bash
pip install -r requirements.txt

export GEMINI_API_KEY="your-key-here"

# Optional — raises rate limits from 60 to 5000 req/hr and enables code search
export GITHUB_TOKEN="your-github-token"
```

## Run

```bash
python main.py path/to/paper.pdf
```

The agent will:
1. Extract and chunk the PDF text
2. Embed chunks and index them in ChromaDB
3. Check the semantic cache for a prior run on the same paper
4. Retrieve the most relevant chunks (RAG)
5. Run a Gemini agent that searches GitHub via tool calls, then generates code
6. Save `generated_implementation.py` and `eval_results.json`

## Suggested papers to try

```bash
# Attention Is All You Need (Transformer)
wget https://arxiv.org/pdf/1706.03762 -O attention.pdf
python main.py attention.pdf

# Word2Vec
wget https://arxiv.org/pdf/1301.3781 -O word2vec.pdf
python main.py word2vec.pdf
```

## Output files

| File | Contents |
|---|---|
| `generated_implementation.py` | Python code produced by the agent |
| `eval_results.json` | RAGAS scores (faithfulness, context relevance, answer relevance) |
| `chroma_db/` | Persisted vector index (reused across runs) |
| `semantic_cache.json` | Cached query → result pairs (skip agent on repeated runs) |

## Architecture

```
PDF
 └─ load & chunk ──→ RAGStore (Gemini embeddings → ChromaDB)
                           │
                    embed query
                           │
               SemanticCache.get() ──→ HIT: return cached code
                           │
                         MISS
                           │
                    RAG retrieve top-k chunks
                           │
                      Gemini Agent
                      ├─ search_github_repositories()  ─┐
                      ├─ search_github_code()            ├── parallel
                      └─ fetch_github_file()            ─┘
                           │
                    Generate Python code
                           │
                 SemanticCache.set() (persist result)
                           │
                  RAGAS Evaluation
                  ├─ Faithfulness
                  ├─ Context Relevance
                  └─ Answer Relevance
```
