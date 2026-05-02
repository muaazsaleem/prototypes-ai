# LLM Non-Determinism & Variance Prototype

This prototype demonstrates a core challenge in applied AI: **Non-Determinism**. Even with the same prompt and parameters, Large Language Models (LLMs) can produce varying outputs across multiple runs.

## The Concept

In production systems, variance is often a bug. If your downstream application expects a specific format or specific keywords, slight variations in LLM responses can break your pipeline.

This experiment compares two strategies:
1.  **Unconstrained Prompting:** Asking the LLM for information without specifying the output format.
2.  **Constrained Prompting:** Using explicit format instructions (e.g., JSON) to "force" the LLM into a more predictable state.

### Why does this happen?
LLMs are probabilistic. They predict the next token based on a probability distribution. When the output format is open-ended, there are many "valid" ways to express the same thought, leading to high variance. By adding constraints, we narrow the probability space for the starting tokens of the response, which often cascades into a more deterministic overall output.

## Setup

1.  **Environment:** Ensure you have Python 3.10+ installed.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **API Key:** Set your Gemini API key in the environment:
    ```bash
    export GEMINI_API_KEY='your_api_key_here'
    ```

## Running the Prototype

Execute the script to see the variance comparison:
```bash
python main.py
```

## Expected Results

- **Strategy A (Unconstrained):** You will likely see higher variance. The LLM might change the phrasing, capitalization, or the way it lists entities in each run.
- **Strategy B (Constrained):** You should see significantly lower variance. By requiring JSON, we anchor the model to a specific structure, which usually results in identical or near-identical outputs across runs.

## Metrics
- **Unique Responses:** The number of different outputs seen across 20 runs.
- **Consistency Score:** The percentage of runs where the most frequent response was returned.
