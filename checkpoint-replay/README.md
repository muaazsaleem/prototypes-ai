# Resumable Conversational AI Agent with Per-Session JSON Checkpointing

This conversational AI agent saves the state of every chat message inside a dedicated JSON file for each session.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key_here"
```

## Running the Agent

Start the agent to list saved sessions or start a new conversation:

```bash
python main.py
```

## Chats

```
session-1

Hello!
My name is Arpit.
/exit
what is my name?
```
