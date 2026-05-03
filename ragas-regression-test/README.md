# RAGAS Regression Test Prototype

This prototype demonstrates how to implement a **regression test** for a RAG (Retrieval-Augmented Generation) pipeline using the **RAGAS** framework. 

In this exercise, we simulate a common production scenario: **reranker optimization**. We measure how reducing the number of retrieved contexts (from 5 to 2) impacts critical retrieval and generation metrics.

## Concept: RAGAS Regression Testing
Regression testing in AI ensures that optimizations (like reducing latency by decreasing context window) do not significantly degrade the quality of the response. We focus on two key RAGAS metrics:

### 1. Context Precision
Measures the retriever's ability to rank **relevant** chunks higher than **irrelevant** ones. It uses the concept of Average Precision, penalizing systems that bury relevant information beneath "noise."

**Calculation Step-by-Step:**
RAGAS uses an LLM to evaluate each retrieved chunk against the Ground Truth to assign a binary relevance verdict ($v_k$: 1 for relevant, 0 for not).

1. **Calculate Precision@k:** For every relevant chunk at rank $k$, calculate the precision up to that point: 
   $$\text{Precision@k} = \frac{\text{Count of relevant chunks in the top } k \text{ results}}{k}$$
2. **Apply Formula:** Sum the Precision@k for all relevant chunks and divide by the total number of relevant chunks in the top K:
   $$\text{Context Precision} = \frac{\sum_{k=1}^{K} (\text{Precision@k} \times v_k)}{\text{Total number of relevant chunks}}$$

*Example: If 5 chunks are retrieved and only ranks 1 and 3 are relevant, the score is $(1.00 + 0.67) / 2 = 0.835$.*

### 2. Faithfulness
Measures the factual consistency of the generated answer against the retrieved context to detect **hallucinations**. If the LLM makes a claim that isn't supported by the context—even if factually true in the real world—it is penalized.

**Calculation Step-by-Step:**
1. **Extract Claims:** An LLM reads the generated answer and breaks it down into a list of standalone "atomic statements" or claims.
2. **Verify Claims (NLI):** The LLM acts as a judge, comparing each claim against the retrieved contexts. It returns a 1 if the context supports the claim, and 0 if it does not.
3. **Apply Formula:**
   $$\text{Faithfulness} = \frac{\text{Number of claims supported by context}}{\text{Total number of claims in the answer}}$$

*Example: If the answer contains 4 distinct claims, but only 3 can be traced back to the retrieved documents, the Faithfulness score is 0.75.*

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
