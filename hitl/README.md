# HITL Content Refiner Prototype

A simple Python-based Human-in-the-loop (HITL) prototype demonstrating iterative content refinement using the Google Gemini API (`google-genai`).

## Why this is a Human-in-the-Loop example

This prototype follows the **"Agentic Tool-Based HITL"** pattern:
1.  **AI Acts as an Agent:** The LLM is provided with a specific tool called `request_human_input`.
2.  **Autonomous Decision to Consult:** The AI evaluates its own confidence. If it detects a gap in its knowledge, it triggers a **Tool Call** instead of generating text.
3.  **Application Mediates:** The Python application intercepts the Tool Call, pauses execution, and presents the AI's question to the user.
4.  **Structured Feedback:** The human's response is packaged as a `function_response` and sent back to the LLM.
5.  **Seamless Integration:** The LLM receives the fact as a "tool result" and incorporates it naturally into the final output.

This pattern is the industry standard for:
- **AI Agents:** Allowing agents to "ask for help" when they hit a roadblock.
- **Data Integrity:** Ensuring that critical facts are sourced from humans via a structured interface.
- **Workflow Automation:** Building complex loops where the AI can conditionally branch based on human decisions.

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -q -U google-genai rich
    ```

2.  **Set API Key:**
    ```bash
    export GEMINI_API_KEY='your-gemini-api-key'
    # Or
    export GOOGLE_API_KEY='your-gemini-api-key'
    ```

3.  **Run the Prototype:**
    ```bash
    python main.py
    ```

## Features
- **Styled UI:** Uses the `rich` library for a professional-grade terminal interface.
- **Stateful Chat:** Uses `client.chats.create` to maintain context across refinement cycles.
- **System Instructions:** Anchors the LLM's persona as a communications expert.
