# Tool Call Error Injection

Demonstrates that tool reliability in an LLM agent depends as much on **error handling instructions** in the system prompt as on the tool implementation itself.

## What it does

The agent has one tool — `get_weather(city)`. It always works on the first call and always returns an HTTP 503 error on the second call.

The same user prompt ("What is the weather in Tokyo and London?") is sent to the model twice:

- **Scenario A** — plain system prompt, no error guidance
- **Scenario B** — system prompt with explicit instructions to acknowledge errors

The code prints tool call counts, success/error counts, the model's final response in each case, and a verdict on whether the error was surfaced to the user.

## Key concept

A tool returning an error does not guarantee the model will tell the user about it. Without explicit instructions, the model may silently skip the failed result, hallucinate data, or bury the failure in vague language. The system prompt is the lever that controls this behavior.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```
