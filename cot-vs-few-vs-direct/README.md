# Prompting Strategy Benchmark: CoT vs. Few-Shot vs. Direct

This prototype demonstrates the performance and cost trade-offs between three common LLM prompting strategies:
1. **Direct Answer**: Asking the model for the answer without any specific reasoning instructions.
2. **Zero-Shot Chain-of-Thought (CoT)**: Instructing the model to "think step-by-step" before answering.
3. **Few-Shot CoT**: Providing 3 examples of step-by-step reasoning followed by a request to reason through the new problem.

## Concept Demonstration
For engineers learning applied AI, this prototype illustrates:
- **Accuracy Improvement**: How reasoning-based prompts (CoT) can solve complex logic problems that simple prompts might fail.
- **Token Overhead**: The cost of "thinking." CoT uses significantly more tokens (output tokens especially) to arrive at an answer.
- **Efficiency Curve**: The trade-off between higher accuracy and higher cost.

## Prerequisites
- Python 3.12+
- `GEMINI_API_KEY` set in your environment.
- Model used: `gemini-2.5-flash`

## Setup and Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Benchmark
Execute the benchmark script:
```bash
python main.py
```

## Outputs
- **Terminal Summary**: A table showing accuracy, total tokens, and tokens per query for each strategy.
- **Visual Results**: A dual-axis plot (`benchmark_results.png`) showing the accuracy-per-token-cost curve.
- **Verdict**: A concise summary of which strategy performed best and which was most token-efficient.

## Benchmark Questions
The prototype uses 5 classic logic and math puzzles, including:
- The bat and ball problem.
- Machine widget production timing.
- Logic puzzles about siblings and sheep.
