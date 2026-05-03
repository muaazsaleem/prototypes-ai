# Semantic Cache Threshold Tuning Prototype

This prototype is a calibration tool designed for the **Applied AI Course**. it demonstrates how to tune the similarity threshold for a semantic cache to balance system performance (Hit Rate) with response quality (Accuracy).

## 1. What this Prototype Does
The prototype simulates a production-grade semantic cache environment. It measures how effectively a cache can identify "duplicate" intents while rejecting "traps" (queries that look similar but have different meanings).

- **Objective**: Find the "Optimal" similarity threshold where we maximize the number of cached responses served without returning incorrect information to the user.
- **Outcome**: A calibration artifact (table and graph) that shows the exact trade-off curve between system efficiency and precision.

## 2. How it Works
The system follows a three-phase execution model:

### Phase A: Dataset Generation
The script uses **Gemini 2.5 Flash** to generate a synthetic test suite of 500 queries:
1.  **Seeds**: Original queries on specific topics.
2.  **Paraphrases**: Rephrased versions of the seeds (these **must** hit the cache).
3.  **Near-Misses**: Queries on the same topic but with different intents (these **must** miss the cache).

### Phase B: Embedding & Vectorization
It converts all 500 queries into high-dimensional numerical vectors using the **`gemini-embedding-2`** model. This allows us to calculate the mathematical "closeness" (Cosine Similarity) between any two queries.

### Phase C: The Threshold Sweep
The prototype iterates through similarity thresholds from **0.70 to 0.95**. For each threshold, it:
1.  Simulates a "First-In" cache population.
2.  Calculates the **Hit Rate**: How many queries were served from cache.
3.  Calculates **Accuracy (Precision)**: How many of those hits were *actually* the correct intent (Seed vs. Paraphrase) vs. how many were "false positives" (Seed vs. Near-Miss).

## 3. How to Read the Calibration
When the script finishes, you will see a **Sensitivity Analysis Table** and a `calibration_curve.png`.

### Interpreting the Metrics
- **Hit Rate (The Efficiency Metric)**: Higher is better. It represents the % of traffic that never hits your expensive LLM/Database.
- **Accuracy (The Quality Metric)**: Higher is better. It represents the % of time the cache returned the *correct* answer.

### Identifying the Zones
- **The Risky Zone (Threshold < 0.80)**: High Hit Rate, but Accuracy drops sharply. This means the cache is "hallucinating" matches and giving users answers to the wrong questions.
- **The Suboptimal Zone (Threshold > 0.92)**: High Accuracy, but Hit Rate is very low. You are paying for an LLM even when the user is asking something you've already answered.
- **The Optimal Zone**: The "Elbow" of the curve. This is usually the highest Hit Rate that maintains **>95% Accuracy**. In this prototype, this typically lands around **0.82 - 0.88**.

## 4. Steps to Run
1.  Ensure `GEMINI_API_KEY` is set in your environment.
2.  Install dependencies: `pip install -r requirements.txt`
3.  Run the sweep: `python main.py`
4.  Examine `calibration_curve.png` for the visual trade-off.
