# Evolving Memory Prototype

A simple Python prototype demonstrating "Evolving Memory" using Gemini 2.0 Flash and the `rich` library.

## Installation

```bash
pip install -q -U google-genai rich
```

## Setup

Set your Gemini API Key:

```bash
export GEMINI_API_KEY='your_api_key_here'
# OR
export GOOGLE_API_KEY='your_api_key_here'
```

## Usage

```bash
python3 main.py
```

## Example Chat Sequences

Use these sequences to observe how memory evolves (new/changed facts will appear in **RED** in the terminal):

### Sequence 1: Location & Role Evolution
```text
I'm Arpit, an engineer from Bangalore.
Actually, I just moved to Bangalore.
I'm now a Principal Engineer 2 working at Razorpay.
```

### Sequence 2: Tech Stack Pivot
```text
I primarily code in Python for AI.
I'm starting to use Rust for performance-critical parts.
```

### Sequence 3: Episodic Memory
```text
I'm meeting Sam at Sourdough Sophia today.
The meeting with Sam is moved to next Tuesday.
Sam can't make it; I'm meeting Sarah instead.
```

## How it Works
The script uses a **System Prompt** that instructs the LLM to:
- Extract **Episodic Facts** from the current message.
- Update the **Long-term Memory** (stored as tuples).
- Resolve contradictions and remove redundant information.
- Maintain a concise, semantic representation of the user's history.
