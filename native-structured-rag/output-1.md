 
╭──────────────────────────────────────────────────────────────────────────────╮
│ Naive RAG vs Structured RAG                                                  │
│ A performance comparison between fixed-chunking and heading-based retrieval. │
╰──────────────────────────────────────────────────────────────────────────────╯

─────────────────────────────────── Document Stats ────────────────────────────────────
  Total chars          : 26,172
  Naive chunks         :  91   (avg   297 chars)
  Structured chunks    :  52   (avg   493 chars)

Embedding all chunks...
   embedding chunk 91/91 ...
   embedding chunk 52/52 ...

-- Q1 ----------------------------------------------------
  Query: What is the p99.9 Target internal processing time for Write Operations?
  Naive      (k=3) q:5/5  sim: 0.77, 0.74, 0.71
    A: The p99.9 Target internal processing time for Write Operations is 250 ms.
  Structured (k=2) q:5/5  rel: 10, 0
    A: The p99.9 Target internal processing time for Write Operations is 250 ms.
  Verdict:   TIE

-- Q2 ----------------------------------------------------
  Query: Does the Free Tier support the RESTORE API operation?
  Naive      (k=3) q:5/5  sim: 0.73, 0.73, 0.72
    A: No, the Free Tier does not support the RESTORE API operation; it is listed as 
"Not applicable" for the Free Tier.
  Structured (k=2) q:5/5  rel: 10, 9
    A: No, the Free Tier does not support the RESTORE API operation. The pricing table 
indicates "Not applicable" for RESTORE under the Free Tier.
  Verdict:   TIE

-- Q3 ----------------------------------------------------
  Query: Should I use the `PUT /v1/buckets/{bucket}/cors` endpoint in my new 
application?
  Naive      (k=3) q:5/5  sim: 0.73, 0.72, 0.68
    A: No, you should not use the `PUT /v1/buckets/{bucket}/cors` endpoint, as CORS is 
now managed via the developer dashboard.
  Structured (k=2) q:5/5  rel: 10, 0
    A: No, you should not use the `PUT /v1/buckets/{bucket}/cors` endpoint in your new 
application, as it is deprecated and CORS is now managed via the developer dashboard.
  Verdict:   TIE

-- Q4 ----------------------------------------------------
  Query: Is the `GET /v1/billing/usage` endpoint officially deprecated?
  Naive      (k=3) q:1/5  sim: 0.70, 0.69, 0.69
    A: The context states that the `GET /v1/billing/usage` endpoint has been "Moved to 
the billing portal API," but it does not explicitly label it as officially deprecated.
  Structured (k=2) q:5/5  rel: 10, 3
    A: Yes, the `GET /v1/billing/usage` endpoint is officially deprecated as it is 
listed under "Deprecated Endpoints" and is scheduled for removal in v3.0.
  Verdict:   STRUCTURED WINS

-- Q5 ----------------------------------------------------
  Query: Is the `DELETE /v1/objects/bulk` endpoint scheduled for removal in v3.0?
  Naive      (k=3) q:1/5  sim: 0.74, 0.70, 0.69
    A: The context states that `DELETE /v1/objects/bulk` should use the lifecycle 
policy API for bulk deletions. It does not specify if this endpoint is scheduled for 
removal in v3.0.
  Structured (k=2) q:5/5  rel: 10, 2
    A: Yes, the `DELETE /v1/objects/bulk` endpoint is scheduled for removal in v3.0.
  Verdict:   STRUCTURED WINS

─────────────────────────────────── Overall Summary ───────────────────────────────────
┏━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Metric      ┃ Naive RAG ┃ Structured RAG ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ Wins        │     0     │       2        │
├─────────────┼───────────┼────────────────┤
│ Ties        │     3     │       3        │
├─────────────┼───────────┼────────────────┤
│ Avg Quality │  3.4 / 5  │    5.0 / 5     │
└─────────────┴───────────┴────────────────┘
