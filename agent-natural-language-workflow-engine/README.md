# Agent Natural Language Workflow Engine

A prototype engine that compiles plain-English descriptions into structured, observable, and durable execution DAGs.

## How it Works

The engine operates in three distinct phases:

### 1. Parsing (The Compiler)
Using Gemini's structured output capability, the engine parses a natural language description into a **Directed Acyclic Graph (DAG)**. It identifies:
- **Nodes**: Individual operations (Fetch, Summarize, Translate, etc.).
- **Dependencies**: Data flow requirements between nodes.
- **Parallelism**: Steps that can run concurrently are automatically identified (those with no shared dependencies).

### 2. Planning (Wave Generation)
The engine topologically sorts the DAG into **Execution Waves**. Nodes in the same wave have their dependencies satisfied and are executed in parallel using `asyncio.gather`.

### 3. Execution (The Runner)
The engine supports two execution modes:
- **Local Async**: A fast, in-memory executor for prototyping.
- **Temporal Orchestration**: A durable, reliable executor that maps nodes to Temporal Activities and manages long-running processes like Human-in-the-Loop (HITL) approvals.

## Key Features

- **Parallel by Default**: Automatically detects and runs independent tasks concurrently.
- **Human-in-the-Loop (HITL)**: Support for `temporal_hitl` nodes that pause execution for human review and approval.
- **Durable Workflows**: Integration with Temporal for reliable execution, retries, and state persistence.
- **Observability**: Built-in OpenTelemetry tracing that emits spans for every node execution.
- **Context Caching**: Uses Gemini's context caching to minimize latency and token usage across multi-step LLM calls.

## Installation

```bash
pip install -r requirements.txt
```

Set your API key:
```bash
export GEMINI_API_KEY="your-api-key"
```

## Usage

### Running a Built-in Example
```bash
# Run the default Hacker News / GitHub digest
python main.py --example 1

# Run the complex Human-in-the-Loop workflow
python main.py --example 2
```

### Running from a Text File
You can write your workflow in plain English in a text file and run it directly:
```bash
python main.py workflow_complex_hitl.txt
```

### Running via Temporal
To use the durable Temporal executor (requires a running [Temporal Server](https://docs.temporal.io/cli/#server)):
```bash
# Start a worker in one terminal (optional implementation placeholder)
# python temporal_executor.py

# Run the workflow via Temporal
python main.py --example 2 --temporal
```

## Project Structure

- `main.py`: CLI entry point and orchestration.
- `parser.py`: NL to DAG compilation logic using Gemini.
- `executor.py`: Local wave-based async executor.
- `temporal_executor.py`: Temporal Workflow and Activity definitions.
- `nodes.py`: Implementation of individual node operations (LLM, Fetch, etc.).
- `models.py`: Pydantic models defining the Workflow and Node schema.
- `tracing.py`: OpenTelemetry setup for observability.
- `cache.py`: Gemini context cache management.
