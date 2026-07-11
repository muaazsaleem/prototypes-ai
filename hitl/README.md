# HITL Safe File Cleaner Prototype

A simplified Python-based Human-in-the-loop (HITL) prototype demonstrating a safe deletion workflow using the Google Gemini API (`google-genai`).

## Why this is a Human-in-the-Loop Deletion example

This prototype follows the **"Agentic Tool-Based HITL Deletion Verification"** pattern:
1.  **AI Evaluates Files:** The LLM is provided with a simulated list of files (some important, some obsolete).
2.  **Autonomous Decision to Delete:** The AI identifies temporary (`.tmp`) or backup (`.bak`) files as candidates for deletion.
3.  **Strict Confirmation Protocol:** When deciding to take action, the LLM must invoke a specific tool (`delete_file`) which contains the instruction: `"Invoke when you decide to take this action."`
4.  **Human Verification:** The Python application intercepts the deletion request, pauses execution, and presents the target file and the AI's logical reason to the human user for approval.
5.  **State Synchronization:** Depending on human input (Yes/No), the file deletion is either executed or rejected, and the status is sent back to the LLM.
6.  **Final Summary:** The LLM finishes processing and prints a final overview of files that were kept vs. deleted.

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
- **System Instruction & Tool Alignment:** Explicitly enforces safe deletion protocol with the exact phrase `"Invoke when you decide to take this action"` in both the system prompt and tool definition.
- **Parallel Tool Support:** Built to handle multiple tool/deletion requests in a single turn.
