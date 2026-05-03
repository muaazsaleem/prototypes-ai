# Tool Schema Calibration Prototype

This prototype demonstrates the impact of **Tool Schema Quality** on LLM selection accuracy. It is designed for students in the Applied AI course to visualize how ambiguous tool descriptions lead to "tool confusion" and how precise descriptions (calibration) solve it.

## The Concept

When an LLM has access to multiple tools with overlapping or vague descriptions, its accuracy in selecting the correct tool drops. This prototype measures this effect by:
1. Running 50 queries against a "Loose" registry (vague descriptions).
2. Running the same 50 queries against a "Tight" registry (disambiguated descriptions).
3. Measuring the **Accuracy Delta (Lift)**.

## Prerequisites

- Python 3.10+
- A Gemini API Key set in your environment: `export GEMINI_API_KEY='your-api-key'`

## Setup

1. Clone or download this folder.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Calibration

Execute the calibration script:
```bash
python main.py
```

## Expected Output

The script will output:
- **Sample Exchanges**: A visual look at how the model interprets queries.
- **Progress Tracking**: Real-time pass/fail status for 50 queries.
- **Summary Table**: Comparison of Loose vs. Tight accuracy scores.
- **Verdict**: A conclusion on the impact of schema quality for this model.

## Why this matters
In production systems, "Tool Selection Error" is a common failure mode. Calibration (tightening descriptions, adding examples, and defining boundaries) is often more effective and cheaper than fine-tuning or using a larger model.
