# Docker Sandbox Execution Monitor

Demonstrates how to build a sandboxed Python execution environment using Docker, instrument it with resource limits, and measure how often each limit is hit in practice.

Gemini 2.5 Flash generates a set of Python code snippets — some benign, some deliberately resource-intensive. Each snippet runs inside a throwaway Docker container with three hard limits enforced. After all runs, hit percentages for each limit are printed in a summary table.

## What it demonstrates

- **Sandboxing**: every snippet runs in an isolated container with `--network=none`, so there is no outbound access
- **Timeout** (10 s): enforced by the `timeout` binary inside the container; exit code 124 signals the kill
- **Memory cap** (512 MB): enforced by Docker's `--memory` flag; the OOM killer terminates the process with exit code 137 when the limit is breached
- **Output cap** (8 000 chars): applied by the host after capturing stdout; output is truncated, not interrupted mid-stream
- **Instrumentation**: every run is classified into one of `clean / timeout / memory / output / error`, and percentages are computed across all runs

## Prerequisites

- Python 3.12+
- Docker Desktop with WSL2 integration enabled (Settings → Resources → WSL Integration → enable your distro), **or** native Docker on Linux/macOS
- `GEMINI_API_KEY` set in your environment

### Enable Docker in WSL2

If `docker --version` fails inside WSL2, open Docker Desktop → Settings → Resources → WSL Integration, toggle on your distro, and click "Apply & Restart".

## Setup

```bash
# Pull the sandbox base image once (avoids cold-start latency during the demo)
docker pull python:3.11-slim

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
export GEMINI_API_KEY="your-key-here"
python main.py
```

## How limits are detected

| Limit | Mechanism | Signal |
|---|---|---|
| Timeout | `timeout 10 python -c …` inside container | exit code 124 |
| Memory | `docker run --memory=512m --memory-swap=512m` | exit code 137 (SIGKILL from OOM killer) |
| Output | host truncates captured stdout at 8 000 chars | stdout length > 8 000 after capture |

## Scenarios

Eight prompts are sent to Gemini, spanning three resource profiles:

- **Clean** — Hello World, Fibonacci(35), Prime Sieve
- **Timeout** — infinite counter loop, 5-billion-iteration summation
- **Memory** — list of 150 million integers
- **Output cap** — printing 200 000 numbers, printing "hello" 100 000 times

## Notes

- Docker startup adds ~1–3 s overhead per run; the subprocess timeout is set to `TIMEOUT_SECONDS + 30` to absorb this
- `--memory-swap` is set equal to `--memory` to disable swap, ensuring the OOM kill fires promptly at 512 MB; on kernels without swap-limit support Docker prints a warning and continues without enforcing the swap cap
- Gemini occasionally wraps code in markdown fences despite the instruction not to; `strip_markdown_fences()` handles this
