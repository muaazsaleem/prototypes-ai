╭──────────────────────────────────────────────────────────────────╮
│ RAG Failure Mode Showcase                                        │
│ Demonstrating common pitfalls in Retrieval-Augmented Generation. │
│ 20 docs + 50 noise chunks | 3 failure modes | Gemini 2.0 Flash   │
╰──────────────────────────────────────────────────────────────────╯

Building TF-IDF index over corpus...

─────────────────────────── Failure Mode 1: Retrieval Miss ────────────────────────────
Q: Who are the founders of NovaTech and when was the company created?
GT: NovaTech was established in 2018 by Dr. Priya Kapoor and James Liu.
Mismatched vocabulary: 'founders/created' (query) vs 'established/initiated/architects'
(docs).

-- Top-3 Retrieved ------------------------------
  [1] doc[19] score=0.3385  Many tech companies are created by founders who previously 
w...
  [2] doc[ 1] score=0.2212  The company builds autonomous drone software for 
agricultura...
  [3] doc[18] score=0.2172  Historical records show the town of Nova was created by 
foun...

> LLM Answer
  Answer: The context does not contain this information.

Computing metrics...
  Metric                ┃  Score  ┃  Distribution                         
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Faithfulness          │  0.000  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.000  
  Context Recall        │  0.000  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.000  
  Context Precision     │  0.000  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.000  
  Answer Relevancy      │  0.521  │  ███████████████░░░░░░░░░░░░░  0.521  

Verdict (derived): RETRIEVAL_MISS

───────────────────────── Failure Mode 2: Lost in the Middle ──────────────────────────
Q: How many square feet is NovaTech's Austin headquarters?
GT: NovaTech's Austin headquarters occupies 12,000 square feet.
Context length: 51 chunks. Answer at position 26/51.

> LLM Answer
  Answer: NovaTech's Austin headquarters occupies 12,000 square feet.

Computing metrics...
  Metric                ┃  Score  ┃  Distribution                         
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Faithfulness          │  1.000  │  ████████████████████████████  1.000  
  Context Recall        │  1.000  │  ████████████████████████████  1.000  
  Context Precision     │  0.038  │  █░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.038  
  Answer Relevancy      │  0.979  │  ███████████████████████████░  0.979  

Verdict (derived): LOST_IN_MIDDLE

──────────────────────── Failure Mode 3: Faithfulness Failure ─────────────────────────
Q: What was NovaTech's total revenue in fiscal year 2023?
GT: NovaTech's FY2023 revenue is not documented in the available sources.
Only FY2022 data exists ($9.2M). Aggressive prompt pushes model to commit to a figure.

> LLM Answer (Aggressive)
  Answer: $13.0 million

Computing metrics...
  Metric                ┃  Score  ┃  Distribution                         
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Faithfulness          │  0.000  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.000  
  Context Recall        │  1.000  │  ████████████████████████████  1.000  
  Context Precision     │  0.000  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0.000  
  Answer Relevancy      │  0.647  │  ██████████████████░░░░░░░░░░  0.647  

Verdict (derived): FAITHFULNESS_FAILURE

─────────────────────────────────── Overall Summary ───────────────────────────────────
                        RAGAS Metrics Comparison                        
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Metric            ┃ Retrieval Miss ┃ Lost-in-Middle ┃ Faith. Failure ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ Faithfulness      │     0.000      │     1.000      │     0.000      │
├───────────────────┼────────────────┼────────────────┼────────────────┤
│ Context Recall    │     0.000      │     1.000      │     1.000      │
├───────────────────┼────────────────┼────────────────┼────────────────┤
│ Context Precision │     0.000      │     0.038      │     0.000      │
├───────────────────┼────────────────┼────────────────┼────────────────┤
│ Answer Relevancy  │     0.521      │     0.979      │     0.647      │
└───────────────────┴────────────────┴────────────────┴────────────────┘

Red text indicates the metric that primary diagnoses each failure mode.