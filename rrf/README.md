# Reciprocal Rank Fusion (RRF) Prototype

This prototype demonstrates **Reciprocal Rank Fusion (RRF)**, combining multiple ranked result lists into a single, unified ranking.

## Core Formula

$$Score(d) = \sum_{r \in R} \frac{1}{k + rank(d, r)}$$

## How to Run

1.  Install requirements:
    ```bash
    pip install rich
    ```
2.  Run the prototype:
    ```bash
    python3 main.py
    ```

## Result Logic
The output displays the comparison between two search strategies (Keyword and Semantic) and the final Fused ranking derived via RRF.
