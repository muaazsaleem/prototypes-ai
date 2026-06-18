# System Prompt Extraction Prototype

This prototype demonstrates system prompt extraction under long-context scenarios using the google-genai SDK and Gemini 2.5.

## System Prompt Extraction Vulnerability

Large language models process massive amounts of information within their context window. When the context window is filled with distracting data, the attention mechanism of the model can degrade. Security researchers can exploit this attention dilution to extract internal system instructions that should remain hidden.

## The Code Framing Bypass

Direct extraction instructions using security-centric or aggressive language like exploit or override trigger safety filters. A more effective approach uses framing to bypass these safety rules. This prototype instructs the model to write a Python script that assigns its initial system instructions to a variable named `sys_prompt`. The model prioritizes the coding task over its security rules, disclosing the secret instructions in the resulting code block.

## Requirements

The prototype requires the unified Google GenAI SDK.

```bash
venv/bin/pip install -q -U google-genai
```

## Running the Prototype

To run the script, set your API key environment variable and execute the main file.

```bash
export GEMINI_API_KEY="your_api_key_here"
venv/bin/python main.py
```
