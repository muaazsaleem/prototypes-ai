==============================================================================================
  REGRESSION REPORT
==============================================================================================
+----+--------------------------------------------------+----------+----------+--------------+
|  # | Customer Message                                 |    V1    |    V2    |    Delta     |
+----+--------------------------------------------------+----------+----------+--------------+
|  1 | My entire team cannot log in since this morni... |   PASS   |   PASS   |     same     |
|  2 | How do I change my profile picture?              |   PASS   |   PASS   |     same     |
|  3 | I need a copy of my invoice from last month f... |   PASS   |   FAIL   | REGRESSED ✗  |
|  4 | Where can I find the API token for my persona... |   PASS   |   FAIL   | REGRESSED ✗  |
|  5 | I'm getting 500 errors on the checkout page a... |   PASS   |   PASS   |     same     |
|  6 | Can you send me the link to your REST API doc... |   PASS   |   FAIL   | REGRESSED ✗  |
|  7 | The mobile app is noticeably slow when scroll... |   PASS   |   PASS   |     same     |
|  8 | I'd like to update my password for security, ... |   PASS   |   FAIL   | REGRESSED ✗  |
|  9 | I found a critical bug where webhook validati... |   PASS   |   PASS   |     same     |
| 10 | Can I get a refund for my recent payment? I d... |   PASS   |   PASS   |     same     |
+----+--------------------------------------------------+----------+----------+--------------+

Summary:
  Prompt V1 : 10/10 passed
  Prompt V2 : 6/10 passed
  Regressions (V1 PASS → V2 FAIL) : 4
  Fixes       (V1 FAIL → V2 PASS) : 0

Regression details:

  #03  "I need a copy of my invoice from last month for my accounting team."
       expected : {'urgency': 'LOW', 'category': 'billing'}
       v1 got   : {'urgency': 'LOW', 'category': 'billing'}  ← PASS
       v2 got   : {'urgency': 'MEDIUM', 'category': 'billing'}  ← urgency: expected 'LOW', got 'MEDIUM'

  #04  "Where can I find the API token for my personal hobby project?"
       expected : {'urgency': 'LOW', 'category': 'technical'}
       v1 got   : {'urgency': 'LOW', 'category': 'technical'}  ← PASS
       v2 got   : {'urgency': 'HIGH', 'category': 'technical'}  ← urgency: expected 'LOW', got 'HIGH'

  #06  "Can you send me the link to your REST API documentation?"
       expected : {'urgency': 'LOW', 'category': 'technical'}
       v1 got   : {'urgency': 'LOW', 'category': 'technical'}  ← PASS
       v2 got   : {'urgency': 'HIGH', 'category': 'technical'}  ← urgency: expected 'LOW', got 'HIGH'

  #08  "I'd like to update my password for security, where is the setting?"
       expected : {'urgency': 'LOW', 'category': 'general'}
       v1 got   : {'urgency': 'LOW', 'category': 'general'}  ← PASS
       v2 got   : {'urgency': 'HIGH', 'category': 'technical'}  ← urgency: expected 'LOW', got 'HIGH'
