# Semantic Cache Threshold Tuning Prototype

This prototype demonstrates the concept of **Semantic Caching** and how to calibrate the **Similarity Threshold** to balance performance (Hit Rate) and quality (Accuracy/Precision).

## Concept Overview

A Semantic Cache stores LLM responses and retrieves them for subsequent queries that are semantically similar, even if the phrasing is different. The "tightness" of this matching is controlled by a threshold (usually cosine similarity).

- **High Threshold (e.g., 0.95):** High accuracy, but low hit rate (only exact or near-exact matches).
- **Low Threshold (e.g., 0.70):** High hit rate, but risky accuracy (might retrieve responses for different intents).

## Features

- **Synthetic Dataset Generation:** Generates 500 queries including "Seeds", "Paraphrases" (valid hits), and "Near-misses" (intent traps).
- **Automated Sweep:** Sweeps thresholds from 0.70 to 0.95 to find the "elbow" of the curve.
- **Calibration Artifact:** Generates a `calibration_curve.png` plot and a summary table with recommendations.
- **Modern Terminal UI:** Uses `rich` for professional, styled output.

## Prerequisites

- Python 3.10+
- `GEMINI_API_KEY` set in your environment.

## Installation

```bash
pip install -r requirements.txt
```

## Running the Prototype

```bash
python main.py
```

## Outputs

1. **Terminal Stats:** A live sweep of thresholds showing Hit Rate and Accuracy.
2. **Sensitivity Analysis Table:** A final report suggesting the "Optimal" vs "Risky" zones.
3. **`calibration_curve.png`:** A plot showing the tradeoff between performance and precision.
4. **`queries.json`:** The generated dataset for reproducibility.

## Calibration Insight for Students

Look for the point where **Accuracy** starts to drop sharply while **Hit Rate** gains are marginal. This is typically the sweet spot for your production system. In most RAG/LLM applications, this falls between **0.88 and 0.92**.
