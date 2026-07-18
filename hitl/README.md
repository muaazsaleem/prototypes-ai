# HITL Safe Command Runner Prototype

A simplified Python-based Human-in-the-loop (HITL) prototype demonstrating a secure, human-approved shell command execution workflow using the Google Gemini API (`google-genai`).

## Why this is a Human-in-the-loop (HITL) Example

This prototype follows the **"Agentic Tool-Based HITL Command Execution Verification"** pattern:
1.  **User Sets the Objective:** The application prompts you to enter an objective of your choice (e.g., `"list the content of the file"`).
2.  **Conversational Follow-ups:** If the objective is ambiguous or requires more detail (e.g., asking *"What is the name of the file you would like to list the content of?"*), the conversational chat loop keeps the session active so you can respond directly.
3.  **AI Analyzes & Plans:** Once the LLM has all necessary information, it determines the appropriate shell commands and plans their execution.
4.  **Prior Human Approval:** Before executing any planned shell command, the LLM must first invoke the `request_human_approval` tool, passing details about the command and why it's needed.
5.  **Human Verification:** The Python application intercepts the approval request, displays the details inside a beautifully formatted console banner, and pauses execution until you approve or deny running the command.
6.  **Strict Execution Protocol:** Only after receiving an approved response from `request_human_approval` can the LLM call the `execute_command` tool.
7.  **Secure Execution:** Any arbitrary shell command passed by the LLM is executed and its results returned, but *only* if explicitly approved by the human operator. If the LLM attempts to run any command without approval, it is rejected.
8.  **Final Summary:** The LLM receives the real command outputs and presents a neat, human-readable summary of the achieved objective.

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
- **Conversational Chat Loop**: Allows multi-turn dialogs where the agent can ask for clarification, request multiple sequential approvals, and execute subsequent commands interactively in a single session.
- **Clean Terminal UI:** Built with `rich` following professional styling rules (Rules, Panels, proper spacing, and semantic colors) to log tool calls and status clearly.
- **Secure Shell Command Execution:** Demonstrates how an agent can be permitted to run shell commands ONLY after explicit human verification.
- **System Instruction & Tool Guardrails:** Explicitly enforces safe system inspection protocols by combining system instructions, required confirmation steps, and programmatic verification inside backend tools.
- **Parallel Tool Support:** Built to handle multiple tool/approval requests in a single turn.
