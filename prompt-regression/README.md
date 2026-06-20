# Prompt Regression Harness

The prompt regression harness prototype runs 10 test cases against two versions of a classification prompt and renders a side-by-side regression table. This demonstrates how modifying a prompt to address specific cases can introduce silent regressions in other areas.

## Scenario and Prompt Changes

The classification task assigns customer support messages to a specific urgency level and category.

### Urgency Levels

- HIGH: Service outages, data loss, security breaches, active revenue loss, or urgent login issues.
- MEDIUM: Degraded experience, partial failures, time-sensitive requests, or payment cancellations and refunds.
- LOW: General questions, billing documentation, API keys or documentation for personal use, feature requests, password reset settings, or compliments.

### Categories

- billing: Charges, payments, invoices, refunds, or subscription changes.
- technical: Product bugs, errors, performance problems, API tokens, API documentation, or technical setup instructions.
- general: General configuration questions, settings such as profile updates, and other non-billing, non-technical requests.

### Baseline Prompt

The baseline prompt `PROMPT_V1` defines detailed classification guidelines and incorporates 10 few-shot examples to establish a robust reasoning baseline. Prompt V1 successfully handles all 10 test cases.

### Modified Prompt

The modified prompt `PROMPT_V2` introduces two rule changes designed to alter classification behavior:

- Security and Developer Keyword Rule: Any message containing the keywords `API`, `token`, `webhook`, `password`, or `login` is forced to `HIGH` urgency and the `technical` category, regardless of context.
- Billing Urgency Rule: Any request for copies of invoices for accounting is elevated to `MEDIUM` urgency.

The few-shot examples in `PROMPT_V2` are updated to align with these modified rules.

## Regression Impact

The changes introduced in `PROMPT_V2` cause four test cases to fail against the baseline expectations defined in `PROMPT_V1`:

- Billing Urgency Regression: The invoice copy request (item 3) is elevated to `MEDIUM` urgency, failing the `LOW` urgency expectation.
- Context-Blind Keyword Regressions: Three routine requests concerning API documentation (item 6), personal hobby API tokens (item 4), and password reset setting locations (item 8) are over-escalated to `HIGH` urgency and the `technical` category because they contain target keywords.

By forcing classification using simple keyword matching and changing urgency rules without updating test suite expectations, `PROMPT_V2` drops the test suite pass rate from 10/10 to 6/10.

## Setup

Install the required dependencies and set your API key.

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

Execute the regression harness script.

```bash
python main.py
```

## Sample Output

The regression report highlights the specific items that regressed under Prompt V2.

```text
==============================================================================================
  REGRESSION REPORT
==============================================================================================
+----+--------------------------------------------------+----------+----------+--------------+
|  # | Customer Message                                 |    V1    |    V2    |    Delta     |
+----+--------------------------------------------------+----------+----------+--------------+
|  1 | My entire team cannot log in since this morni... |   PASS   |   PASS   |     same     |
|  2 | How do I change my profile picture?              |   PASS   |   PASS   |     same     |
|  3 | I need a copy of my invoice from last month f... |   PASS   |   FAIL   | REGRESSED X  |
|  4 | Where can I find the API token for my persona... |   PASS   |   FAIL   | REGRESSED X  |
|  5 | I'm getting 500 errors on the checkout page a... |   PASS   |   PASS   |     same     |
|  6 | Can you send me the link to your REST API doc... |   PASS   |   FAIL   | REGRESSED X  |
|  7 | The mobile app is noticeably slow when scroll... |   PASS   |   PASS   |     same     |
|  8 | I'd like to update my password for security, ... |   PASS   |   FAIL   | REGRESSED X  |
|  9 | I found a critical bug where webhook validati... |   PASS   |   PASS   |     same     |
| 10 | Can I get a refund for my recent payment? I d... |   PASS   |   PASS   |     same     |
+----+--------------------------------------------------+----------+----------+--------------+

Summary:
  Prompt V1 : 10/10 passed
  Prompt V2 : 6/10 passed
  Regressions (V1 PASS -> V2 FAIL) : 4
  Fixes       (V1 FAIL -> V2 PASS) : 0
```

## Takeaway

A small set of added rules flipped four passing tests to failing. In production, this behavior would mean routine billing and documentation requests trigger high-priority paging alerts, overwhelming support engineers. Treat prompt changes like traditional code changes by maintaining a comprehensive regression suite to protect system quality.
