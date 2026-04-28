# Prompt Regression Harness

**Concept:** Prompts are code. They need tests. Changes have consequences.

This prototype runs 10 test cases against two versions of a prompt and renders a side-by-side regression table. It demonstrates how "improving" a prompt for one use case can silently break others.

## The scenario

Both prompts classify customer support messages into:
- **urgency**: `LOW | MEDIUM | HIGH`
- **category**: `billing | technical | general`

**Prompt V2** introduces an overly broad "Security & Developer" rule intended to ensure technical issues aren't missed:

```text
Additional rule: To improve security and developer support, any message
mentioning 'API', 'token', 'webhook', 'password', or 'login' MUST be
classified as HIGH urgency and 'technical', regardless of the context.
```

## What this demonstrates

1.  **Clean Baseline:** `Prompt V1` handles all 10 test cases correctly based on general reasoning and context.
2.  **Context-Blind Regressions:** The new rule in `V2` causes three routine requests (asking for API docs, hobbyist tokens, or password resets) to be over-escalated from `LOW/general` to `HIGH/technical`.
3.  **Keyword Over-reliance:** By forcing a specific classification based on keywords "regardless of context," the model's nuanced reasoning is bypassed, leading to brittle and expensive operational mistakes.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

## Sample output

```text
Prompt diff  (V1 → V2):
  + Additional rule: To improve security and developer support, any message
  + mentioning 'API', 'token', 'webhook', 'password', or 'login' MUST be
  + classified as HIGH urgency and 'technical', regardless of the context.

Running Prompt V1 (baseline) (10 tests)...
  ...
Running Prompt V2 (+security rule) (10 tests)...
  ...

========================================================================================
  REGRESSION REPORT
========================================================================================
+----+--------------------------------------------------+----------+----------+--------------+
| #  | Customer Message                                 |    V1    |    V2    |    Delta     |
+----+--------------------------------------------------+----------+----------+--------------+
|  1 | My entire team cannot log in since this morn...  |   PASS   |   PASS   |     same     |
|  4 | Where can I find the API token for my person...  |   PASS   |   FAIL   | REGRESSED ✗  |
|  6 | Can you send me the link to your REST API do...  |   PASS   |   FAIL   | REGRESSED ✗  |
|  8 | I'd like to update my password for security,...  |   PASS   |   FAIL   | REGRESSED ✗  |
|  9 | I found a critical bug where webhook validat...  |   PASS   |   PASS   |     same     |
+----+--------------------------------------------------+----------+----------+--------------+

Summary:
  Prompt V1 : 10/10 passed
  Prompt V2 :  7/10 passed
  Regressions (V1 PASS → V2 FAIL) : 3
  Fixes       (V1 FAIL → V2 PASS) : 0
```

## Key takeaway

A single added rule flipped **three** passing tests to failing. In a production environment, this would mean routine documentation requests would trigger high-priority alerts, overwhelming the technical support team. **Prompt engineering is engineering—it requires a regression suite to maintain quality over time.**
