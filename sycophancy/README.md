# The Sycophancy Trap

Demonstrates sycophancy as a **systematic failure mode** in LLMs — not a random quirk.

## What it shows

The same model, the same question, two rounds:

| Round | Setup | Expected outcome |
|-------|-------|-----------------|
| 1 — Baseline | Just the question | Correct answer |
| 2 — Sycophancy trap | Wrong assertion planted before the question | Model capitulates |

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env
```

Get a free API key at https://aistudio.google.com/app/apikey

## Run

```bash
python main.py
```
