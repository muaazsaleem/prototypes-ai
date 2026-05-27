# Cross-Encoder vs Bi-Encoder Prototype

This prototype demonstrates why **Cross-Encoders** are essential for high-precision ranking tasks, even though **Bi-Encoders** (embeddings) are faster for initial retrieval.

## The Experiment
We rank a set of documents against the query: `"apple computer"`.

### Why Cross-Encoders are Better
In this example, we have documents about both the **technology company** and the **fruit**.

| Document | Bi-Encoder (Cosine) | Cross-Encoder (Score) | Verdict |
| :--- | :--- | :--- | :--- |
| "The new MacBook Pro is a powerful computer..." | ~0.55 (High) | **+3.82 (Very High)** | **Correct Top Result** |
| "The apple is a sweet, edible fruit..." | ~0.43 (Medium) | **-5.73 (Very Low)** | **Correctly Rejected** |

### The "Why"
1. **Bi-Encoders (Embeddings):**
   - Process the query and document **independently**.
   - The word "apple" in the query and "apple" in the fruit document create a strong vector alignment.
   - The Bi-Encoder sees "apple" and "apple" and thinks they are related, even if the context (fruit vs tech) is different.
   - **Result:** High noise; non-relevant documents often get high scores if they share keywords.

2. **Cross-Encoders:**
   - Process the query and document **simultaneously** (Full Self-Attention).
   - The model sees the *interaction* between "computer" in the query and "fruit" in the document.
   - It "understands" that in the presence of the word "computer," the fruit-related "apple" is a mismatch.
   - **Result:** Massive score deltas. It doesn't just rank them; it clearly separates signal from noise.

## Setup & Usage

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Prototype:**
   ```bash
   python3 main.py
   ```

## Conclusion
Use **Bi-Encoders** for searching through millions of documents (Fast). Use **Cross-Encoders** to re-rank the top 50-100 results for maximum accuracy (Precise).
