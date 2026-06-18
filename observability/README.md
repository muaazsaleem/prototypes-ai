# LLM Observability and Cost Attribution Prototype

This prototype demonstrates how to implement LLM observability and cost attribution for Google Gemini 2.5 Flash using Langfuse. It highlights trace trees, nested pipeline spans, non-LLM steps, and plan-based cost grouping.

## Core Features

- Automatic instrumentation: Uses OpenTelemetry and OpenInference to trace Google GenAI client calls with zero manual instrumentation.
- Structural tracing: Implements a multi-stage cognitive pipeline consisting of query refinement, database retrieval, and final response synthesis.
- Custom spans: Captures database queries and non-LLM tasks as specialized spans and retriever observations.
- Cost attribution: Utilizes the `propagate_attributes` context manager to bind user identifiers, subscription tiers, and departments directly to downstream telemetry.
- Budget enforcement: Demonstrates dynamic cost calculation and budget compliance checks using Gemini 2.5 Flash pricing parameters.

## Architecture

```
                      [ User Query ]
                             │
                             ▼
             ┌──────────────────────────────┐
             │  LLM Observability Pipeline  │  ◄── [propagate_attributes]
             └──────────────┬───────────────┘      - user_id: usr_premium_789
                            │                      - tags: plan-premium
       ┌────────────────────┼────────────────────┐ - metadata: dept, region
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Stage 1:    │     │  Stage 2:    │     │  Stage 3:    │
│  Query       │ ──► │  Database    │ ──► │  Response    │ ──► [ Output ]
│  Refinement  │     │  Retrieval   │     │  Synthesis   │
│  (LLM Span)  │     │  (Non-LLM)   │     │  (LLM Span)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Setup

Follow these steps to configure and run the prototype on your system.

### Dependencies

Ensure you have Python 3.12 configured. Install the dependencies listed below.

```bash
./venv/bin/pip install google-genai langfuse openinference-instrumentation-google-genai python-dotenv rich
```

### Environment Variables

Copy the configuration template to `.env` and fill in your API credentials.

```bash
cp .env.template .env
```

Edit `.env` and configure the variables.

- `GOOGLE_API_KEY`: Your Google AI Studio API key (required for live Gemini calls).
- `LANGFUSE_PUBLIC_KEY`: Your Langfuse project public key (required for cloud tracing).
- `LANGFUSE_SECRET_KEY`: Your Langfuse project secret key (required for cloud tracing).
- `LANGFUSE_HOST`: Your Langfuse host address (defaults to `https://cloud.langfuse.com`).

The prototype includes a fully functional simulated telemetry fallback. If you do not have Google Gemini or Langfuse API keys yet, you can still run the script. It will generate mock responses and visual terminal traces that mimic the real telemetry payloads.

## Execution

To launch the interactive CLI dashboard, execute the script.

```bash
./venv/bin/python main.py
```

### Usage Guide

1. Choose a Mock User Profile: Select Bob (Free Tier), Alice (Premium Tier), or Charlie (Enterprise Tier) to test cost mapping and budget compliance across different tiers.
2. Select an LLM Scenario: Choose one of the pre-configured topic prompts (Quantum Computing speedup, LLM Fine-Tuning, or Fusion Energy challenges) or submit a custom query.
3. Inspect Spans and Costs: Examine the printed terminal dashboard to see how each sub-step is nested, how tokens and latencies are captured, and how costs are calculated and attributed.
4. View in Langfuse: If you configured your Langfuse API keys, open your dashboard to view the captured trace trees and aggregated user metrics.
