# Fact-Checking Agent

Verifies factual claims in a passage using pure prompting — no external tools, no search APIs.

## How it works

1. **Decompose** — splits the passage into atomic, independently verifiable claims
2. **Evidence** — for each claim, asks the model to recall supporting and contradicting evidence from its parametric knowledge
3. **Self-consistency voting** — runs 5 independent model calls per claim at high temperature, takes the majority verdict as the final answer, and expresses calibrated confidence as a fraction of agreeing votes
4. **Report** — displays per-claim panels with evidence, vote distribution, and an overall credibility score

## Project structure

```
agent-fact-checking/
├── config.py       # model name, voting rounds, temperature settings
├── models.py       # dataclasses: Claim, Evidence, VoteResult, FactCheckReport
├── decomposer.py   # LLM call: passage → list of atomic claims
├── evidence.py     # LLM call: claim → supporting + contradicting evidence
├── voter.py        # self-consistency voting: N independent calls → majority verdict
├── reporter.py     # assemble and display the final report with rich
└── main.py         # entry point — orchestrates the pipeline
```

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
# Run with the built-in sample passage
python main.py

# Run with your own passage
python main.py "The Eiffel Tower was built in 1889 and stands 330 meters tall. It was designed by Gustave Eiffel for the 1900 World's Fair."
```

## Concepts demonstrated

- **Claim decomposition** — breaking prose into minimal verifiable units
- **Self-consistency voting** — sampling a model N times and aggregating responses to reduce variance and produce calibrated confidence
- **Structured output** — using `response_mime_type="application/json"` for reliable JSON extraction
- **Calibrated confidence** — expressing uncertainty as a fraction of agreeing model calls rather than a raw probability
