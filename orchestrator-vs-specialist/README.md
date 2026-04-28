# Orchestrator and Specialist Pattern (Complex)

Demonstrates a sophisticated multi-agent system using **deeply nested schema contracts**.

An **Orchestrator** manages a multi-step pipeline to generate a technical whitepaper:
1.  **Planner Specialist**: Receives a topic and generates a `Blueprint` (structured outline with research goals).
2.  **Researcher Specialist**: The Orchestrator iterates over the blueprint, calling the researcher for *each* section to produce `SectionResearch` (structured facts, sources, and confidence scores).
3.  **Writer Specialist**: Receives the full blueprint and aggregated research to synthesize the `FinalDocument`.

## Why Schema Contracts Matter

As multi-agent systems grow, they accumulate state. In this example, the Orchestrator accumulates research data to feed to the Writer. If a specialist silently changes its output format, it breaks the pipeline's assumptions.

| Phase | What happens |
|-------|-------------|
| **Phase 1 — Contract Honored** | Planner -> Iterative Research -> Writer. All agents adhere to Pydantic schemas. Pipeline completes successfully. |
| **Phase 2 — Contract Broken** | The Researcher Specialist is "updated" to return `facts` as a list of strings instead of `Fact` objects. The Orchestrator catches this immediately during validation, preventing corrupted data from reaching the Writer. |

## Schema Contracts (Pydantic)

The system relies on deeply nested models:
- `Blueprint`: Contains a list of `SectionPlan`.
- `SectionResearch`: Contains a list of `Fact` objects (claim, source, confidence).
- `FinalDocument`: The complex final result.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

## Run

```bash
python main.py
```

## Expected output

1. **Phase 1 Execution**:
   - Outgoing/Incoming logs for Planner.
   - Iterative Research logs for each planned section.
   - Final synthesized Whitepaper.
2. **Phase 2 Execution**:
   - The Researcher returns a broken format.
   - **Validation Table**: Shows exactly which field (nested inside the list) failed and why.
   - Graceful pipeline abortion.
