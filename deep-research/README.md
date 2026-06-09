```
ps -T -p $(pgrep -f "python main.py")
```

# Multi-Agent Deep Research Engine

This project is a pedagogical prototype demonstrating multi-agent orchestration, fork-join parallel execution, and sequential quality gatekeeping patterns using Python and the Gemini 2.5 Flash model.

## Overview

The Deep Research Engine takes a broad research topic from the user and executes a complete, structured, multi-phase research pipeline. Rather than relying on a single prompt or a sequential agent loop, this prototype implements a parallelized agentic system. It assigns specialized roles to different instances of Gemini 2.5 Flash, configures specific tools, coordinates concurrent operations, and aggregates raw data into a definitive research document.

## Architecture

The system coordinates four distinct agent roles through a structured pipeline:

```
                ┌─────────────────────────┐
                │   Lead Planner Agent    │  (Generates structured Research Plan)
                └────────────┬────────────┘
                             │  Split & Dispatch (Parallelism)
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌───────────────────┐         ┌───────────────────┐
    │ Web Search Agent  │         │ Concept Specialist│  (Executes in parallel)
    │ (Google Grounded) │         │ (Internal Brain)  │
    └─────────┬─────────┘         └─────────┬─────────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼  Wait & Synchronize (Handoff)
                ┌─────────────────────────┐
                │  Research Critic Agent  │  (Finds gaps & alignment issues)
                └────────────┬────────────┘
                             │  Audit Feedback Handoff
                ┌─────────────────────────┐
                │ Lead Synthesizer Agent  │  (Generates final master markdown)
                └─────────────────────────┘
```

The pipeline progresses through four sequential phases:

- Phase 1: Planning. The Lead Planner Agent analyzes the user topic and breaks it down into a structured blueprint of two or three complementary, non-overlapping sub-tasks. It outputs the plan as a JSON object conforming to a schema defined via Pydantic.
- Phase 2: Parallel Execution. The system forks execution into concurrent research tasks. The Web Search Agent is configured with the Google Search grounding tool to fetch up-to-date facts, statistics, and records. The Concept Specialist Agent relies on its internal training data to unpack underlying theoretical frameworks and concepts. Both tasks execute concurrently without blocking each other.
- Phase 3: Quality Audit. The parallel reports are synchronized and passed to the Research Critic Agent. This agent conducts a critical evaluation, identifying information gaps, structural misalignment, and any logical contradictions between the web research and the conceptual model.
- Phase 4: Synthesis. The Lead Synthesizer Agent receives the original topic, the raw reports, and the Critic feedback. It compiles and refines the material into a single, cohesive, publication-quality document saved as `research_report.md`.

## Key Patterns Demonstrated

The engine serves as a reference implementation for several modern agentic patterns:

- Fork-Join Concurrency. Demonstrates how to dispatch multiple asynchronous tasks using `asyncio.gather` and run synchronous network calls in background threads using `asyncio.to_thread` to maximize throughput.
- Structured output schema. Employs Pydantic models with the `response_schema` parameter in the Gemini API to guarantee type-safe, parseable JSON blueprints for execution.
- Tool-Based Specialization. Shows how to selectively enable search grounding tools for specific tasks while leaving reasoning agents ungrounded to leverage pure theoretical knowledge.
- Cross-Agent Quality Review. Demonstrates how a specialized critic agent can serve as a quality gatekeeper, auditing the work of other agents before compiling a final product.

## Prerequisites

To run this application, you must have:

- Python 3.10 or higher
- A valid Gemini API key set as an environment variable

## Installation

Follow these steps to set up the project environment and install dependencies.

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install google-genai rich
   ```

## Usage

Set your Gemini API key in your terminal session:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Run the research pipeline by passing a topic as an argument:

```bash
python main.py "The current state of quantum computing in 2026"
```

If no topic is passed, the script prompts you to enter one interactively.

Upon completion, the application displays a summary of execution metrics showing the clock time saved via parallel execution, along with a preview of the generated report. The complete document is saved as `research_report.md` in the root directory.
