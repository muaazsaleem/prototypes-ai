╭──────────────────────────────────────────────────────────────────────╮
│ LLM Variance & Determinism Prototype                                 │
│ Demonstrating the impact of output constraints on response variance. │
│ Model: gemini-2.5-flash | 20 runs per strategy                       │
╰──────────────────────────────────────────────────────────────────────╯

-- Strategy A: Unconstrained Prompt --------------------------------------
Running 20 iterations...
╭──────────────────────────────────────────────── Model Input ────────────────────────────────────────────────╮
│                                                                                                             │
│  USER: Extract the sentiment and key entities from this customer review: 'The new                           │
│        smartphone is amazing, the camera quality is top-notch but the battery life                          │
│        is a bit disappointing. I love the design though!'                                                   │
│                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭────────────────────────────────────────────── Model Response ───────────────────────────────────────────────╮
│                                                                                                             │
│  ASSISTANT: **Sentiment:** Mixed  **Key Entities and their Sentiments:** *   **Smartphone                   │
│             (general):** Positive ("amazing") *   **Camera Quality:** Positive                              │
│             ("top-notch") *   **Battery Life:** Negative ("disappointing") *                                │
│             **Design:** Positive ("love")                                                                   │
│                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Collecting remaining responses:
  Run #02: o  4.1s     Run #03: o  3.5s     Run #04: o  4.0s   
  Run #05: o  4.6s     Run #06: o  4.8s     Run #07: o  4.9s     Run #08: o  4.3s   
  Run #09: o  3.7s     Run #10: o  5.7s     Run #11: o  4.1s     Run #12: o  3.6s   
  Run #13: o  3.9s     Run #14: o  4.8s     Run #15: o  4.1s     Run #16: o  4.0s   
  Run #17: o  4.0s     Run #18: o  3.3s     Run #19: o  3.7s     Run #20: o  3.4s   

-- Strategy B: Constrained (JSON) Prompt --------------------------------------
Running 20 iterations...
╭──────────────────────────────────────────────── Model Input ────────────────────────────────────────────────╮
│                                                                                                             │
│  USER: Extract the sentiment and key entities from this customer review: 'The new                           │
│        smartphone is amazing, the camera quality is top-notch but the battery life                          │
│        is a bit disappointing. I love the design though!' Output only a JSON object                         │
│        with the keys 'sentiment' and 'entities'. 'sentiment' should be a string                             │
│        (Positive, Negative, or Mixed). 'entities' should be a list of strings.                              │
│                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭────────────────────────────────────────────── Model Response ───────────────────────────────────────────────╮
│                                                                                                             │
│  ASSISTANT: ```json {   "sentiment": "Mixed",   "entities": [     "smartphone",     "camera                 │
│             quality",     "battery life",     "design"   ] } ```                                            │
│                                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Collecting remaining responses:
  Run #02: o  2.2s     Run #03: o  1.8s     Run #04: o  2.2s   
  Run #05: o  2.4s     Run #06: o  1.6s     Run #07: o  1.9s     Run #08: o  2.3s   
  Run #09: o  1.9s     Run #10: o  2.0s     Run #11: o  1.9s     Run #12: o  2.3s   
  Run #13: o  2.0s     Run #14: o  2.3s     Run #15: o  2.3s     Run #16: o  2.0s   
  Run #17: o  2.8s     Run #18: o  1.9s     Run #19: o  2.6s     Run #20: o  2.3s   

─────────────────────────────────────────────── Overall Summary ───────────────────────────────────────────────

                                         Variance Comparison                                         
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Metric                   ┃ Strategy A (Unconstrained) ┃ Strategy B (Constrained) ┃ Delta / Impact ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ Unique Responses         │             20             │            1             │      -19       │
├──────────────────────────┼────────────────────────────┼──────────────────────────┼────────────────┤
│ Consistency Score (%)    │            5.0%            │          100.0%          │     +95.0%     │
└──────────────────────────┴────────────────────────────┴──────────────────────────┴────────────────┘

VERDICT: Output constraints significantly reduced variance and improved determinism.
