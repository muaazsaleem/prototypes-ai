# Reflexion Prototype

Demonstrates **Reflexion** — an agentic pattern where a model attempts a task, analyzes its failures, and uses those insights to improve in the next attempt. This process compounds within a single session but resets between runs.

## Concept

Reflexion is a self-correction loop. When an agent fails a task, it doesn't just try again blindly. Instead, it:
1.  **Attempts** the task.
2.  **Evaluates** the result against test cases.
3.  **Reflects** on the specific failures to diagnose root causes.
4.  **Implements** a fix based on its own reflection.

## What This Prototype Does

The agent is tasked with implementing a Python function `merge_intervals(intervals)`, a classic algorithm with well-known edge cases. 

### The Challenge
Merge intervals has enough edge cases (touching boundaries, unsorted input, deep containment) that first attempts often miss 2–3 tests. 

To make the Reflexion loop even more visible, this prototype includes **Hidden Requirements** that are not mentioned in the initial prompt:
- **Input Validation**: Handling `None` as input (should return an empty list).
- **Type Coercion**: Handling lists containing string integers (e.g., `["1", "3"]`) or mixed types.

The agent will likely fail these tests on the first attempt, then use its own reflection to discover and implement the necessary validation and casting logic.

Across 3 attempts:
1.  **Attempt 1**: Cold start.
2.  **Attempt 2**: Uses reflection from Attempt 1.
3.  **Attempt 3**: Uses reflections from both prior attempts.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Set your Gemini API key:
    ```bash
    export GEMINI_API_KEY=your_key_here
    ```

## Run

```bash
python main.py
```

## Expected Output

- **Model Input/Response Panels**: Visualizing the raw conversation.
- **Evaluation Results**: PASS/FAIL status for 8 test cases.
- **Reflection Note**: The model's internal monologue and plan for the next attempt.
- **Performance Summary**: A table showing the "Lift" in accuracy across iterations.

## Why This Works
This prototype uses `gemini-2.0-flash`, which is fast and capable of following the iterative feedback loop. The combination of logical edge cases and explicit failure feedback provides a robust testbed for demonstrating in-session learning.
