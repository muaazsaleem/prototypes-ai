# Few-Shot with Self-Consistency

Demonstrates how few-shot examples and self-consistency (majority vote over multiple samples) progressively improve classification accuracy — a cheap accuracy boost before you reach for fine-tuning.

**Task:** Customer review sentiment classification → `positive` / `negative` / `neutral`

## Three stages

| Stage | Technique | How it works |
|---|---|---|
| 1 | Zero-shot | Plain prompt, no examples, `temp=0` |
| 2 | Few-shot | 3 labelled examples in the prompt, `temp=0` |
| 3 | Self-consistency | Few-shot sampled 5× at `temp=0.7`, majority vote wins |

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

## What you'll see

For each stage the script prints every prediction with a ✓/✗ marker. Stage 3 also shows all 5 votes per sample so you can watch the majority-vote mechanic in action. A summary table at the end shows the accuracy delta between stages.

```
════════════════════════════════════════════════════════════════
  ACCURACY SUMMARY
════════════════════════════════════════════════════════════════
  Zero-shot         : 60.0%
  Few-shot          : 73.3%   (+13.3% vs zero-shot)
  Self-consistency  : 80.0%   (+6.7% vs few-shot  |  +20.0% vs zero-shot)
════════════════════════════════════════════════════════════════
```

The test set contains 15 reviews — 5 easy cases and 10 deliberately ambiguous ones where the gains are most visible.
