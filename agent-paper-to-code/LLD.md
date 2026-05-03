# Low-Level Design: Paper-to-Code Agent

The **Paper-to-Code Agent** is an autonomous system designed to ingest academic research papers (PDFs) and generate functional Python implementations of the core algorithms described within them. It leverages Retrieval-Augmented Generation (RAG), agentic reasoning with tool use, and a semantic caching layer for efficiency.

---

## 1. Architecture Overview

The system follows a modular pipeline architecture divided into four distinct phases:
1.  **Ingestion & Metadata:** Extracting text and high-level context from the PDF.
2.  **RAG Indexing:** Vectorizing and storing paper content for granular retrieval.
3.  **Logic Generation:** An agentic loop that uses retrieved context and external tools (GitHub) to write code.
4.  **Evaluation:** Assessing the generated code using RAGAS-inspired metrics.

---

## 2. Key Components

### 2.1 PDF Processor (`pdf_processor.py`)
- **Responsibility:** Handles raw document ingestion.
- **Functions:**
    - `load_pdf`: Extract text using `pypdf`.
    - `chunk_text`: Implements a sliding window approach (fixed-size with overlap) to preserve context boundaries.
    - `extract_paper_metadata`: Uses Gemini to identify the paper title and core method, providing the "north star" for the agent.

### 2.2 RAG Store (`rag.py`)
- **Responsibility:** Provides "long-term memory" of the paper.
- **Technology:** `ChromaDB` (persistent) and `gemini-embedding-001`.
- **Mechanism:** Uses cosine similarity to find the most relevant paper excerpts for a given implementation query.

### 2.3 Semantic Cache (`semantic_cache.py`)
- **Responsibility:** Minimizes redundant LLM calls and latency.
- **Mechanism:** Stores (Query Embedding, Query Text, Generated Code) triples. A lookup is successful if the cosine similarity between the current query embedding and a cached embedding exceeds a threshold (0.90).

### 2.4 Agent Loop (`agent.py`)
- **Responsibility:** Orchestrates the reasoning and implementation process.
- **Model:** `gemini-2.5-flash`.
- **Feature: Parallel Tool Execution**: Uses a `ThreadPoolExecutor` to execute multiple tool calls concurrently within a single turn, significantly reducing execution time when the agent performs multiple searches.

### 2.5 Tools (`tools.py`)
- **Responsibility:** Enables the agent to interact with the external world (GitHub).
- **Tools:**
    - `search_github_repositories`: Finds relevant projects.
    - `search_github_code`: Searches for specific implementation patterns.
    - `fetch_github_file`: Retrieves raw source code for study.

### 2.6 Evaluator (`evaluator.py`)
- **Responsibility:** Automated quality assurance.
- **Metrics (RAGAS-inspired):**
    - **Faithfulness:** Does the code match the paper's claims?
    - **Context Relevance:** Was the retrieved context actually useful?
    - **Answer Relevance:** Does the code fully address the user's request?

---

## 3. Data & Execution Flow

### 3.1 Data Flow
`PDF` → `Raw Text` → `Metadata & Text Chunks` → `Vector Embeddings (ChromaDB)` → `Contextual Excerpts` → `Agent Prompt` → `Generated Python Code` → `Evaluation JSON`.

### 3.2 Execution Flow
1.  **Phase 1: Ingestion**
    - The PDF is loaded and split into 1500-character chunks with a 200-character overlap.
    - Metadata (Title, Method) is extracted using an initial LLM call.
2.  **Phase 2: RAG Indexing**
    - Chunks are embedded and indexed into ChromaDB.
3.  **Phase 3: Generation**
    - A search query is formulated from the metadata.
    - **Cache Lookup:** If a similar query exists in `semantic_cache.json`, the cached code is returned immediately.
    - **Retrieval:** If a miss, the top-K relevant chunks are retrieved.
    - **Agent Loop:** The agent receives the paper excerpts and uses GitHub tools to research existing patterns. It iterates (up to 6 turns) until it produces the final Python code.
4.  **Phase 4: Evaluation**
    - The generated code is evaluated against the retrieved context and original query.
    - Results are saved to `eval_results.json` and displayed in a formatted table.

---

## 4. Core Configuration (`config.py`)

The system's behavior is tunable through several key parameters:
- `CHUNK_SIZE` (1500) & `CHUNK_OVERLAP` (200): Define the granularity of the RAG index.
- `TOP_K_CHUNKS` (5): The number of paper excerpts provided to the agent as context.
- `CACHE_SIMILARITY_THRESHOLD` (0.90): The cosine similarity required for a semantic cache hit.
- `GEMINI_MODEL` (gemini-2.5-flash): The primary reasoning engine.

---

## 5. Design Decisions & Patterns

- **Parallelism:** The agent can issue multiple `function_call` requests in one turn. The system executes these in parallel using Python's `concurrent.futures`.
- **State Management:** The agent loop maintains conversation history (`contents` list) to allow multi-turn reasoning and tool-result integration.
- **LLM-as-Judge:** The evaluator uses the LLM to score its own output based on predefined rubrics, mimicking the RAGAS framework.
- **Decoupled Tools:** Tools are registered in a `TOOL_REGISTRY`, making it easy to add new capabilities (e.g., ArXiv search, Python REPL) without modifying the core agent logic.
