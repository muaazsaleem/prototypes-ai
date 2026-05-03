# RAG Chunking Strategy Comparison

This prototype demonstrates and compares three different text chunking strategies for Retrieval-Augmented Generation (RAG):

1.  **Fixed-Size Chunking**: Splits text into chunks of a constant number of words/tokens.
2.  **Semantic Chunking**: Groups sentences based on their semantic similarity using embeddings.
3.  **Parent-Child Chunking**: Indexes small "child" chunks for retrieval but returns larger "parent" chunks to the LLM for better context.

## Prerequisites

- Python 3.10+
- Gemini API Key set in environment as `GEMINI_API_KEY`

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Prototype

1.  **Prepare Data**: This script extracts text from the PDF and generates evaluation queries using Gemini 2.5 Flash.
    ```bash
    python prepare_data.py
    ```

2.  **Compare Strategies**: This script runs the evaluation across the three strategies.
    ```bash
    python main.py
    ```

## Evaluation Methodology

- The prototype uses the first 5 pages of the provided NIST technical document.
- It evaluates retrieval precision using 5 generated queries.
- For each query, Gemini 2.5 Flash acts as a "judge" to determine if the retrieved context contains the necessary information to answer the question.

## Output

The script outputs a comparison table with retrieval "Hits" and "Precision %" for each strategy, concluding with a final verdict on which strategy performed best for the given document and queries.
