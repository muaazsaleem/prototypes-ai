# Skill Executor

Demonstrates multi-step AI skill decomposition using Gemini 2.5 Flash.

A **Skill** is a typed, reusable unit: a name, a description, and a sequence of steps, each with a focused prompt template and a strict JSON output schema. The **Skill Executor** runs each step, validates its output against the schema at the boundary, retries with an error-correction prompt on failure, and pipes the validated output into the next step as context.

The prototype runs the `repo-health-audit` skill on three real GitHub repos:

| Repo | Character |
|---|---|
| `tiangolo/fastapi` | Healthy, actively maintained |
| `docopt/docopt` | Neglected — last meaningful commit ~2013 |
| `django/django` | Large, monorepo-scale |

## What it demonstrates

1. **Skill decomposition keeps each Gemini call small** — each of the 5 steps has a single concern and a narrow output schema, making it easy to inspect and debug.
2. **Schema validation at step boundaries** — every step's JSON output is validated with `jsonschema` before it feeds into the next step. A bad response triggers an error-correction retry rather than silently propagating bad data.
3. **Critic sub-step catches hallucinated dependency versions** — after `dependency_check`, a focused critic prompt re-examines the version numbers and flags anything that looks invented or inconsistent.
4. **Token cost comparison** — the full skill run (5 steps + critic) is compared token-for-token against a single monolithic prompt attempting the same job.

## Steps in `repo-health-audit`

```
clone_repo → static_analysis → dependency_check (+critic) → test_coverage → synthesise
```

Each step only receives the fields it needs from previous steps — nothing more.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set your API key:

```bash
export GEMINI_API_KEY="your-key-here"
```

## Run

```bash
python main.py
```

The run takes ~3–5 minutes (18 Gemini calls total: 5 steps × 3 repos + 1 critic per repo + 1 monolithic per repo).

## Output structure

- Per-repo: each step's model input and response panels, schema validation result, and token counts.
- After `dependency_check`: the critic sub-step verdict and any flagged items.
- After all steps: a health report with score, verdict, and prioritised remediation table.
- Final section: token cost table (per-step vs monolithic) and a cross-repo comparison summary.
