# Multi-Agent Code Reviewer

An orchestrator fans out a PR diff to three specialist agents (style, security, logic). A critic-refiner agent consolidates the findings and produces a single coherent review. A memory layer keeps past decisions per repository so the system stays consistent across PRs. Checkpointing ensures a specialist failure does not restart the entire review.

## Architecture

```
PR Diff
   │
   ├──► Style Agent      ──┐
   ├──► Security Agent   ──┼──► Critic-Refiner ──► Final Review
   └──► Logic Agent      ──┘         ▲
                                     │
                              Repository Memory
```

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
# Review the built-in sample diff (auth module with intentional bugs)
python main.py

# Review your own diff file
python main.py --diff path/to/your.diff

# Scope the review to a specific repository (for memory)
python main.py --repo my-org/my-repo --diff path/to/your.diff
```

## Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point and terminal display |
| `orchestrator.py` | Coordinates the three phases of the pipeline |
| `agents.py` | LLM calls for each specialist and the critic |
| `models.py` | Dataclasses: Finding, SpecialistReport, ReviewDecision |
| `memory.py` | Per-repo persistent review history |
| `checkpoint.py` | Per-specialist checkpoint so partial runs resume |
| `sample_diff.py` | Built-in demo diff with style, security, and logic issues |

## How Checkpointing Works

Each review run gets a short ID derived from `sha256(repo + diff)`. After a specialist finishes, its result is saved to `checkpoints/<review_id>/<agent>.json`. On re-run, completed specialists are skipped. Delete the `checkpoints/` directory to start fresh.

## How Memory Works

After each review, the verdict and key decisions are appended to `memory/<repo>.json` (last 5 reviews kept). The critic agent receives this history and is instructed not to contradict it, so style standards stay consistent across PRs.
