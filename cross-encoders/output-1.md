╭────────────────────────────────────────────────────────────────────╮
│ Cross-Encoder vs Bi-Encoder Prototype                              │
│ Demonstrating the precision of cross-encoders in semantic ranking. │
│ Task: Rank documents for the query "apple computer"                │
╰────────────────────────────────────────────────────────────────────╯

────────────────────────────────────────────────────────────────────────────────────── Bi-Encoder (Embedding-based Search) ──────────────────────────────────────────────────────────────────────────────────────
-- Encoding and Computing Cosine Similarity ----------------
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 2442.56it/s]
────────────────────────────────────────────────────────────────────────────────────── Cross-Encoder (Direct Interaction) ───────────────────────────────────────────────────────────────────────────────────────
-- Re-ranking Query-Document Pairs ------------------------
Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 105/105 [00:00<00:00, 2804.88it/s]
────────────────────────────────────────────────────────────────────────────────────────────── Comparative Results ──────────────────────────────────────────────────────────────────────────────────────────────

                                                   Query: "Does aspirin treat headaches?"                                                   
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Rank ┃ Bi-Encoder (Cosine Similarity)                                  ┃ Cross-Encoder (Relevance Score)                                 ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│  1   │ Clinical trials show that aspirin treats headaches by reduci... │ Clinical trials show that aspirin treats headaches by reduci... │
│      │ Score: 0.8856                                                   │ Score: 10.4427                                                  │
├──────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│  2   │ Aspirin is a highly effective medication used to treat heada... │ To treat a headache, doctors often recommend aspirin or rest... │
│      │ Score: 0.8318                                                   │ Score: 8.6778                                                   │
├──────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│  3   │ To treat a headache, doctors often recommend aspirin or rest... │ Aspirin is a highly effective medication used to treat heada... │
│      │ Score: 0.7931                                                   │ Score: 8.6529                                                   │
├──────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│  4   │ A severe headache is a known rare side effect of taking aspi... │ Taking aspirin for a headache should be done with food to av... │
│      │ Score: 0.7719                                                   │ Score: 8.2450                                                   │
├──────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│  5   │ Headaches are often caused by stress, not a lack of aspirin.... │ A severe headache is a known rare side effect of taking aspi... │
│      │ Score: 0.7471                                                   │ Score: 7.6150                                                   │
├──────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│  6   │ Taking aspirin for a headache should be done with food to av... │ Headaches are often caused by stress, not a lack of aspirin.... │
│      │ Score: 0.7379                                                   │ Score: 6.2027                                                   │
└──────┴─────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘
