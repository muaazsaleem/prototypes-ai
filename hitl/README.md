# HITL Safe File Cleaner Prototype

A simplified Python-based Human-in-the-loop (HITL) prototype demonstrating a safe deletion workflow using the Google Gemini API (`google-genai`).

## Why this is a Human-in-the-Loop Deletion example

This prototype follows the **"Agentic Tool-Based HITL Deletion Verification"** pattern:
1.  **AI Evaluates Files:** The LLM is provided with a simulated list of files (some important, some obsolete).
2.  **Autonomous Decision to Delete:** The AI identifies temporary (`.tmp`) or backup (`.bak`) files as candidates for deletion.
3.  **Prior Human Approval Request:** The LLM must first invoke the `request_human_approval` tool, passing details about the action, file name, and logical reason.
4.  **Human Verification:** The Python application intercepts the approval request, pauses execution, and asks the human operator to approve or deny the action.
5.  **Strict Deletion Protocol:** Only after receiving an approved response from `request_human_approval` can the LLM call the `delete_file` tool to execute the actual deletion. If the LLM attempts to call `delete_file` without prior approval, the application rejects the deletion and returns an error.
6.  **State Synchronization:** Depending on human input, the file status is updated and sent back to the LLM.
7.  **Final Summary:** The LLM finishes processing and prints a final overview of files that were kept vs. deleted.

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
- **Clean Terminal UI:** Built with `rich` for elegant, readable console feedback.
- **System Instruction & Tool Guardrails:** Explicitly enforces safe deletion protocol by combining system instructions, a required approval step (`request_human_approval`), and programmatic verification inside `delete_file`.
- **Parallel Tool Support:** Built to handle multiple tool/approval requests in a single turn.
