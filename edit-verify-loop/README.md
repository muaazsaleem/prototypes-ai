# Edit-Verify Loop Agent

A three-phase mini-agent that autonomously fixes a buggy Python source file by
iterating between code generation and test verification — up to five times.

## Concept

The agent runs a tight loop:

```
Phase 1  Read the failing test file and the source file it tests
Phase 2  Ask Gemini to generate an edit to the source file
Phase 3  Run pytest, parse the output, log the result delta
         └─ repeat until all tests pass or MAX_ITERATIONS reached
```

This pattern shows the simplest form of an **agentic feedback loop**: the model
doesn't just produce output once — it reads the environment (test results),
acts (edits the file), observes consequences (new test results), and loops.

### Key ideas demonstrated

- **Tool use as verification** — pytest is the tool; its output is the reward signal
- **Context accumulation** — each iteration sends the updated source + latest test
  failures back to the model, so it can track its own progress
- **Delta tracking** — the agent logs how many tests each edit fixes or breaks,
  making the improvement trajectory visible

## Files

| File | Purpose |
|---|---|
| `main.py` | The agent: phases 1–3, the loop, and the summary |
| `sample_source.py` | Intentionally buggy Python module (the agent's target) |
| `sample_test.py` | Pytest suite — 16 tests, 9 initially failing |

## Setup

```bash
pip install -r requirements.txt
```

Set your Gemini API key:

```bash
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

The agent overwrites `sample_source.py` in place on each iteration. To reset
between runs, restore it from git:

```bash
git checkout sample_source.py
```
