# Minimal Search Agent Prototype

This prototype demonstrates a minimal **Reason + Act (ReAct)** agent loop in Python. It is designed to help engineers understand the core mechanics of autonomous agents without the abstraction of complex frameworks.

## Core Concept: The Search-Read-Decide Loop

The agent operates in a continuous loop until it reaches a conclusion:
1.  **Question:** The user provides an initial query.
2.  **Reason:** The LLM evaluates the question and decides whether it can answer immediately or needs more information.
3.  **Action:** If more info is needed, the LLM generates a search query.
4.  **Observation:** The system executes the search and provides the result back to the LLM.
5.  **Termination:** The loop ends when the LLM provides a final answer or reaches the iteration limit.

## Key Features

-   **Live Search:** Integrated with DuckDuckGo for real-time information retrieval.
-   **Structured I/O:** Visualizes the "thought process" of the model using Rich panels.
-   **Safe Execution:** Implements a hard turn limit to prevent infinite loops.
-   **Readable Code:** Fully commented and formatted for educational clarity.

## Setup and Running

### 1. Environment Variables
Ensure your Gemini API key is available in your environment:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Agent
```bash
python main.py
```

## Implementation Notes

-   **Model:** Uses `gemini-2.5-flash` for high-speed reasoning.
-   **Search:** Uses the `duckduckgo-search` (DDGS) library to fetch snippets from the web.
-   **Loop Logic:** The core agent logic resides in the `run_agent` function, spanning approximately 20 lines.
