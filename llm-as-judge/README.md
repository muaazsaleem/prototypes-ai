# LLM-as-Judge: Positional Bias Exposure

Demonstrates that LLM judges are not neutral. The same response is scored differently depending on where it appears in the judge prompt. A structured rubric partially controls this bias.

## Concept

When you use an LLM to evaluate a list of candidate outputs:

1. **Positional bias** — early positions may be scored higher or lower simply because of recency/primacy effects and how the model weighs context.
2. **Context contamination** — neighbour quality bleeds into scores; a weak response surrounded by strong ones is judged more harshly than the same response alone.
3. **Rubric as mitigation** — explicit scoring criteria anchor each level to observable properties, giving the judge less room to be swayed by position.

## What the prototype does

| Phase | What happens |
|-------|-------------|
| 1 | Generates 10 diverse candidate responses to the same task |
| 2a | Judges all 10 with a **simple, vague prompt** (original order) |
| 2b | Judges the same list with positions 1 and 6 **physically swapped** |
| 3a | Judges with a **rubric prompt** (original order) |
| 3b | Judges the same swapped list with the rubric |

Scores are re-aligned back to the original output identity after each swap, then compared. The delta shows positional bias; the difference in deltas between phases 2 and 3 shows rubric effectiveness.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

## Output

- Progress dots while generating 10 candidate outputs
- Full LLM input/output panels for each of the 4 judge calls
- Per-output score comparison tables (original vs. swapped order)
- Summary table: mean absolute score delta for swapped vs. non-swapped outputs, simple prompt vs. rubric
- Final verdict: whether the rubric reduced positional bias

## Key insight

If the judge were perfectly neutral, swapping the position of an output would not change its score. In practice it does — that gap is positional bias. The rubric reduces (but rarely eliminates) the gap because anchored criteria make the judge less sensitive to contextual signals like position.
