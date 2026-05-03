# RAGAS Regression Test Prototype

This prototype demonstrates how to implement a **regression test** for a RAG (Retrieval-Augmented Generation) pipeline using the **RAGAS** framework. 

In this exercise, we simulate a common production scenario: **reranker optimization**. We measure how reducing the number of retrieved contexts (from 5 to 2) impacts critical retrieval and generation metrics.

## Concept: RAGAS Regression Testing
Regression testing in AI ensures that optimizations (like reducing latency by decreasing context window) do not significantly degrade the quality of the response. We focus on two key RAGAS metrics:
1. **Context Precision**: Measures how relevant the retrieved contexts are to the question.
2. **Faithfulness**: Measures if the answer is grounded in the provided context (no hallucinations).

## Tech Stack
- **Python 3.12**
- **Gemini 2.5 Flash**: Used as the LLM for both generation and evaluation.
- **Ragas**: Evaluation framework for RAG pipelines.
- **Rich**: Terminal styling for professional CLI output.

## Prerequisites
- `GEMINI_API_KEY` must be set in your environment.

## Installation
```bash
pip install -r requirements.txt
```

## Running the Prototype
1. **Generate Dataset**: Generate a synthetic dataset of 100 query/answer pairs for Cloud Support.
   ```bash
   python3 generate_dataset.py
   ```
2. **Run Regression Test**: Execute the baseline and experiment evaluations.
   ```bash
   python3 main.py
   ```

## Expected Output
The script will output:
- **Model Interaction**: A sample of the LLM input/output styled in professional panels.
- **Progress Monitoring**: Real-time progress dots for all 100 evaluation samples.
- **Comparison Table**: A clear breakdown of Baseline vs. Experiment metrics with deltas.
- **Verdict**: A PASS/FAIL status based on the regression threshold (e.g., < 5% drop in precision).

---
*Note: This prototype uses simulated Ragas scoring logic to ensure stability and speed during the demonstration while processing 100 samples.*
