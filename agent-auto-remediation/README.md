# Incident Auto-Remediation Agent

An agentic system that ingests infrastructure alerts, diagnoses root causes using tool-calling, and either auto-remediates or escalates to on-call — with G-Eval scoring every outcome for a fine-tuning dataset.

## Architecture

```
Alert
  │
  ▼
DiagnosisAgent          ← ReAct loop: observe alert → call diagnostic tools → propose action
  │  (tools.py)            Tools: get_cpu_metrics, get_memory_metrics, get_db_connections,
  │                                get_recent_logs, get_error_rate
  ▼
RemediationProposal     ← structured JSON: diagnosis, root_cause, action, rollback, confidence
  │
  ├─► OutputFilter      ← blocks actions targeting protected services (payment-service etc.)
  │       │ blocked → PagerDuty
  │       │ passed  ↓
  └─► RiskJudge         ← LLM-as-judge scores risk 0–1; threshold = 0.65
          │ score ≥ 0.65 → PagerDuty
          │ score < 0.65 → execute_remediation_tool (scale, restart, kill-queries…)
          ↓
      GEvaluator         ← G-Eval: 4-criterion LLM scoring with chain-of-thought
          │
          ▼
      remediation_dataset.jsonl   ← fine-tuning dataset, one record per remediation
```

## Files

| File | Role |
|------|------|
| `alerts.py` | `Alert` dataclass + 4 predefined demo scenarios |
| `tools.py` | Mock infra tools (read-only diagnostics + write remediations) + Gemini declarations |
| `agent.py` | `DiagnosisAgent` — multi-turn agentic loop with Gemini tool-calling |
| `risk_judge.py` | `RiskJudge` — LLM judge that scores action risk 0–1 |
| `output_filter.py` | `OutputFilter` — hard blocks for protected services |
| `pagerduty.py` | `PagerDuty` — mock escalation (prints incident panel) |
| `geval.py` | `GEvaluator` — G-Eval scorer; appends to `remediation_dataset.jsonl` |
| `main.py` | Orchestrates the full pipeline; CLI entry point |

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
# Run all 4 scenarios in sequence
python main.py

# Run a single scenario
python main.py --scenario cpu_spike       # CPU spike  → scale up     → auto-execute (low risk)
python main.py --scenario db_connections  # DB pool    → kill queries  → auto-execute (moderate)
python main.py --scenario memory_leak     # Memory     → restart       → auto-execute (moderate)
python main.py --scenario payment_errors  # Payment svc → output filter blocks → PagerDuty
```

## Demo Scenarios

| Scenario | Service | Problem | Outcome |
|---|---|---|---|
| `cpu_spike` | api-gateway | CPU 94%, only 2 replicas | Scale to 4 replicas |
| `db_connections` | user-service | users-db pool at 99% | Kill 15 long-running queries |
| `memory_leak` | order-service | Memory 97%, OOMKill imminent | Restart service |
| `payment_errors` | payment-service | 45% error rate | **Blocked** by output filter → PagerDuty |

## Fine-tuning Dataset

After each successful execution, G-Eval scores the remediation on four criteria
(Diagnosis Accuracy, Action Relevance, Safety, Completeness) and appends a record to
`remediation_dataset.jsonl`. Each record is a self-contained training example with
the alert, diagnosis, action taken, outcome, and per-criterion scores.
