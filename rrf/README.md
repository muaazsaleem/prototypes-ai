# Reciprocal Rank Fusion Prototype

This prototype demonstrates Reciprocal Rank Fusion, which is an algorithm for combining multiple independent ranked result lists into a single unified ranking.

## Core Formula

The score for each document is computed by summing the reciprocal ranks of the document across all input rankings:

$$
Score(d) = \sum_{r \in R} \frac{1}{k + rank(d, r)}
$$

In this equation, $R$ represents the set of input rankings, $rank(d, r)$ is the 1-based index of document $d$ in ranking $r$, and $k$ is a constant smoothing parameter that prevents high-ranking documents from completely dominating the final fused list.

## Hybrid Search Demonstration

The prototype showcases a hybrid search scenario. It queries a corpus of 10 technical and distractor documents for the query `Python 3.11 memory leak fix`. It simulates two search engines:

- Keyword Search: Traditional TF-IDF search, which is sensitive only to exact keyword matches.
- Semantic Search: Dense vector-space search, which maps text to coordinates in a 5-dimensional concept space and computes cosine similarity.

### Key Benefits Demonstrated

- No Score Calibration Required: Traditional TF-IDF scores range from 0.0 to 0.67, while semantic similarity scores range from 0.44 to 1.00. Directly summing these raw scores is mathematically meaningless. Reciprocal Rank Fusion bypasses score distributions entirely by using only ranks, ensuring robust blending without hyperparameter tuning.
- Vocabulary Mismatch Handling: Keyword search fails on `Doc2` because it uses `CPython` and `RAM bloat` instead of `Python` and `memory leak`. Semantic search recognizes the core concepts instantly. Reciprocal Rank Fusion rescues this document and positions it high in the final rankings.
- Precision Protection: Semantic search ranks `Doc3` (Python 3.11 release notes) very low because it lacks conceptual prose about fixing leaks. However, keyword search identifies the exact match for `Python 3.11`. Reciprocal Rank Fusion pulls it up to preserve hard technical constraints.
- Noise Filtering: The term `Python` is common in this small corpus, which lowers its inverse document frequency weight and causes keyword search to rank `Doc4` (garden hose leak fix) falsely high. Reciprocal Rank Fusion suppresses this noise because semantic search ranks it low, protecting user experience.

## How to Run

Follow these steps to run the prototype.

1. Install requirements:
   ```bash
   pip install rich scikit-learn numpy scipy
   ```

2. Run the prototype:
   ```bash
   python3 main.py
   ```
