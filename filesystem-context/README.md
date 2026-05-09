# Prototype: Structured Project Index Agent

This prototype demonstrates a foundational concept in agentic systems: Context Management via Lazy Indexing and Token Optimization. It uses Gemini 2.5 Flash to analyze code files, build a structured project index, and answer user queries efficiently.

## What This Prototype Does

Instead of sending an entire codebase to the LLM on every turn, which is slow and token-expensive, this agent builds a lightweight index in `project_index.json`. It then uses this index to answer queries, demonstrating massive token savings.

1. Lazy Indexing: The agent only reads and processes files like `sample_math.py`, `sample_utils.py`, and `sample_data_parser.py` when they are first encountered.
2. Staleness Checks: Before querying the LLM, the agent compares the file's last modified timestamp (`mtime`) on disk against the `last_read` timestamp in its index cache.
3. Structured Metadata Extraction: When a file is processed, the LLM is instructed to return a structured JSON response containing:
- `summary`: A high-level explanation of the file's purpose.
- `symbols`: Key functions, classes, and variables found in the file.
4. Token Optimization and Querying: Instead of injecting raw code to answer a user's question, the agent injects only the lightweight JSON index. The script calculates and displays the exact number of tokens saved using this approach.

## Setup and Requirements

1. API Key: Ensure you have a valid `GEMINI_API_KEY` set in your environment.

```bash
export GEMINI_API_KEY="your_api_key_here"
```

2. Dependencies: Install the required packages. This prototype uses `google-generativeai`, `rich` for terminal styling, and `black` for code formatting.

```bash
pip install -r requirements.txt
```

## How to Run and Demonstrate

Execute the main script.

```bash
python project_indexer_agent.py
```

### Demonstration Steps for Students

1. Phase 1: Lazy Indexing: On the first run, the agent detects the sample files as stale or new. It sends prompts to Gemini to build the index. On subsequent runs, it marks the files as fresh and bypasses the LLM entirely for indexing.
2. Phase 2: Token Optimization Analysis: The script compares the token count of the raw source code against the token count of the generated JSON index. This table visually proves why sending an index is vastly cheaper and faster than sending raw files.
3. Phase 3: Querying the Project: The agent is given a complex query: "I need to parse a CSV file and then calculate the sum of a specific column. Which files and functions should I use from this project?" It successfully answers this query by reading *only* the lightweight JSON index context, without ever looking at the raw code.
4. Cache Invalidation: Open `sample_data_parser.py` and make a tiny edit like adding a comment line and save the file. Run the script again. The agent will detect `sample_data_parser.py` as stale and re-index it via the LLM, but will successfully reuse the cache for the other files.

## Output Interpretation

- Model Input/Response: Grey panels showing exactly what was sent to and received from Gemini, simulating agentic internal monologues and I/O.
- Token Comparisons: A clean table showing the difference between the Naive Approach and the Agentic Approach.
- Verdict: Final pass or fail status based on successful indexing and query resolution.
