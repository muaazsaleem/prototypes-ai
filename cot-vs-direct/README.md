# Chain-of-Thought vs. Direct Answer

Demonstrates that **"think step by step"** is a reliability lever, not just a stylistic preference. 

Modern, highly-capable models like Gemini 2.0 Flash easily ace classic textbook riddles zero-shot from memory. To truly demonstrate the power of Chain-of-Thought (CoT), this script runs the model against a suite of **algorithmic tasks** that defeat zero-shot memorization and require genuine multi-step execution.

For each of the 5 algorithmic tasks, the script calls Gemini **10 times** with a direct-answer prompt and **10 times** with a chain-of-thought prompt. It scores every response and shows the accuracy distribution side-by-side, so you see consistency — not just a single lucky or unlucky example.

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

Total runtime: ~4–5 minutes (100 API calls with small delays to respect rate limits).

## What to look for

| Problem | Why it's interesting |
|---|---|
| **Spatial Navigation (Grid)** | Requires keeping track of a continuous X/Y coordinate state and heading across multiple directional changes. |
| **Relational Logic (Family Tree)** | Forces the model to step through generational kinship layers rather than collapsing them via semantic association. |
| **Temporal Scheduling** | Requires constraint satisfaction where the placement of one entity limits the placement of others. |
| **Inventory State Tracking** | Pushes the model to handle sequential add/remove/swap mutations on an array of objects. |
| **Logic Puzzle (Truth-Tellers)** | Requires testing multiple boolean hypotheses against contradictory statements to find the single valid state. |

## Key takeaway

CoT reliability shows up in the *distribution*, not in a single run. A model can get any of these right once by chance. The 10-run score reveals which prompting strategy is actually robust when tasked with novel algorithmic logic.
