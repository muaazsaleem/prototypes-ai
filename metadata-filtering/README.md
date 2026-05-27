# Metadata Filtering Prototype

This prototype demonstrates how to use an LLM (Gemini) to extract filtering criteria from a user query and apply those filters to metadata before performing RAG.

## Problem
Naive RAG (Retrieval-Augmented Generation) often relies purely on semantic similarity. When a user asks for "Q1 2026", the semantic search might retrieve "Q1 2025" because they are semantically similar. This leads to hallucinations where the LLM answers based on the wrong year's data.

## Solution: Metadata Filtering
1. **Extract Filters**: Use Gemini to identify filter criteria (e.g., Year, Quarter, Department) from the natural language query.
2. **Apply Filters**: Programmatically filter the documents based on their metadata before the LLM even sees them.
3. **Enriched Context**: Pass the metadata along with the content to the LLM to ensure it has full context for disambiguation.

## How to Run

1. **Install dependencies**:
   ```bash
   pip install -q -U google-genai
   ```

2. **Set your API Key**:
   ```bash
   export GOOGLE_API_KEY='your-api-key'
   ```

3. **Run the demo**:
   ```bash
   python3 main.py
   ```

## Demo Scenario
The script compares a "Naive" search (where it gets all documents) vs a "Filtered" search (where it only gets the correct year). It uses documents where the content itself is ambiguous (doesn't mention the year), proving that metadata is essential for accurate retrieval.
