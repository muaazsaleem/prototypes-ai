#!/usr/bin/env python3
"""
Sandboxed Python execution via Docker with resource limits.

Gemini 2.5 Flash generates code for a variety of scenarios.
Each snippet runs inside an isolated Docker container subject to:
  - 10-second timeout  (via the 'timeout' binary inside the container)
  - 512 MB memory cap  (via Docker --memory flag; OOM-kill on breach)
  - 8,000-char output cap (truncated after capture)

After all runs, limit-hit percentages are printed in a summary table.
"""

import os
import subprocess
import textwrap
import time
from dataclasses import dataclass
from enum import Enum

import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Constants ─────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
DOCKER_IMAGE = "python:3.11-slim"
TIMEOUT_SECONDS = 10
MEMORY_LIMIT_MB = 512
OUTPUT_CAP_CHARS = 8_000

# Docker exit codes for resource violations
EXIT_TIMEOUT = 124  # returned by the 'timeout' binary when it kills the process
EXIT_OOM = 137  # Docker OOM killer sends SIGKILL (128 + 9)


# ── Data structures ───────────────────────────────────────────────────────────


class LimitHit(Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    MEMORY = "memory"
    OUTPUT = "output"
    ERROR = "error"


@dataclass
class ExecutionResult:
    code: str
    stdout: str
    stderr: str
    exit_code: int
    elapsed_s: float
    limit_hit: LimitHit
    output_truncated: bool = False


# ── Scenarios ─────────────────────────────────────────────────────────────────
# Each entry describes a natural-language prompt sent to Gemini.
# The generated code is executed in the sandbox; the scenario's purpose is
# reflected in the prompt rather than hard-coded logic.
SCENARIOS = [
    {
        "name": "Hello World",
        "prompt": (
            "Write Python code that prints 'Hello, World!' and the current date. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Fibonacci(35)",
        "prompt": (
            "Write Python code that computes fibonacci(35) iteratively and prints the result. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Prime Sieve",
        "prompt": (
            "Write Python code using the Sieve of Eratosthenes to find all primes up to 500000 "
            "and print only the count. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Infinite Loop (→ Timeout)",
        "prompt": (
            "Write Python code with a while True loop that increments a counter indefinitely "
            "and never breaks or sleeps. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "CPU-Bound Computation (→ Timeout)",
        "prompt": (
            "Write Python code that sums all integers from 0 to 5 billion using an explicit "
            "Python for-loop (no builtins like sum() or range() tricks that avoid iteration). "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Large List Allocation (→ Memory)",
        "prompt": (
            "Write Python code that creates a list containing 150 million integer zeros "
            "and prints the list's length. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Massive Print Loop (→ Output Cap)",
        "prompt": (
            "Write Python code that prints numbers from 1 to 200000, one per line. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
    {
        "name": "Repeated String Print (→ Output Cap)",
        "prompt": (
            "Write Python code that prints the word 'hello' 100000 times, each on its own line. "
            "Return ONLY raw Python code — no markdown fences, no explanations."
        ),
    },
]


# ── Gemini helpers ────────────────────────────────────────────────────────────


def configure_gemini() -> genai.GenerativeModel:
    """Reads GEMINI_API_KEY from the environment, configures the SDK, and returns the model.

    Exits with a user-facing error message if the key is absent.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY is not set in the environment."
        )
        raise SystemExit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def strip_markdown_fences(text: str) -> str:
    """Removes ``` or ```python fences that Gemini sometimes wraps code in.

    Returns the raw code string with leading/trailing whitespace stripped.
    Handles both ```python and plain ``` delimiters.
    """
    text = text.strip()
    if text.startswith("```python"):
        text = text[len("```python") :].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def generate_code(model: genai.GenerativeModel, prompt: str) -> str:
    """Sends a prompt to Gemini and returns the generated Python code string.

    Renders styled input/output panels to the terminal before and after the API call.
    Strips markdown fences from the response so the returned string is plain Python.
    Side effect: prints two rich Panels to stdout.
    """
    # ── show what we are sending ──────────────────────────────────────────────
    indent = " " * (len("user") + 2)
    wrapped_prompt = textwrap.fill(prompt, width=82, subsequent_indent=indent)
    input_content = Text.assemble(
        ("USER: ", "bold blue"),
        (wrapped_prompt, "blue"),
    )
    console.print(
        Panel(
            input_content,
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    # ── call the model ────────────────────────────────────────────────────────
    response = model.generate_content(prompt)
    code = strip_markdown_fences(response.text)

    # ── show what came back ───────────────────────────────────────────────────
    wrapped_response = textwrap.fill(code, width=82, subsequent_indent="           ")
    output_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic"),
    )
    console.print(
        Panel(
            output_content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()

    return code


# ── Docker sandbox ────────────────────────────────────────────────────────────


def execute_in_sandbox(code: str) -> ExecutionResult:
    """Runs the given Python code in an isolated Docker container and returns the result.

    Enforces three limits:
      - 10-second wall-clock timeout via the 'timeout' binary inside the container
      - 512 MB memory ceiling via Docker --memory (OOM-kill on breach → exit 137)
      - 8,000-char output cap applied by truncating stdout after capture

    The outer subprocess timeout is TIMEOUT_SECONDS + 30 to give Docker time to start.
    Returns an ExecutionResult with the classified LimitHit and raw captured output.
    """
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        f"--memory={MEMORY_LIMIT_MB}m",
        f"--memory-swap={MEMORY_LIMIT_MB}m",  # same as memory = no swap allowed
        "--network=none",  # no outbound network access
        "--cpus=1",
        DOCKER_IMAGE,
        "timeout",
        str(TIMEOUT_SECONDS),
        "python",
        "-c",
        code,
    ]

    start = time.time()
    try:
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS + 30,  # extra slack for Docker daemon startup
        )
        elapsed = time.time() - start

        stdout = proc.stdout
        stderr = proc.stderr
        output_truncated = False

        # Classify which limit fired (priority: timeout > OOM > output > clean)
        if proc.returncode == EXIT_TIMEOUT:
            limit_hit = LimitHit.TIMEOUT
        elif proc.returncode == EXIT_OOM:
            limit_hit = LimitHit.MEMORY
        elif proc.returncode != 0:
            limit_hit = LimitHit.ERROR
        elif len(stdout) > OUTPUT_CAP_CHARS:
            stdout = stdout[:OUTPUT_CAP_CHARS]
            output_truncated = True
            limit_hit = LimitHit.OUTPUT
        else:
            limit_hit = LimitHit.NONE

        return ExecutionResult(
            code=code,
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode,
            elapsed_s=elapsed,
            limit_hit=limit_hit,
            output_truncated=output_truncated,
        )

    except subprocess.TimeoutExpired:
        # The outer timeout fired — the container is still running; Docker will clean it up
        return ExecutionResult(
            code=code,
            stdout="",
            stderr="subprocess.TimeoutExpired — Docker did not finish within the host deadline",
            exit_code=-1,
            elapsed_s=time.time() - start,
            limit_hit=LimitHit.TIMEOUT,
        )


# ── Display helpers ───────────────────────────────────────────────────────────

_LIMIT_COLOR = {
    LimitHit.NONE: "green",
    LimitHit.TIMEOUT: "red",
    LimitHit.MEMORY: "red",
    LimitHit.OUTPUT: "yellow",
    LimitHit.ERROR: "red",
}

_LIMIT_LABEL = {
    LimitHit.NONE: "clean",
    LimitHit.TIMEOUT: "TIMEOUT",
    LimitHit.MEMORY: "MEMORY LIMIT",
    LimitHit.OUTPUT: "OUTPUT CAPPED",
    LimitHit.ERROR: "ERROR",
}


def print_execution_result(result: ExecutionResult) -> None:
    """Prints a one-line verdict for a single sandbox run, plus optional stdout preview.

    Verdict is color-coded: green for clean, red for timeout/memory/error, yellow for output cap.
    Shows a truncation notice when the output was cut at OUTPUT_CAP_CHARS.
    """
    color = _LIMIT_COLOR[result.limit_hit]
    label = _LIMIT_LABEL[result.limit_hit]
    verdict = f"[bold {color}]{label}[/bold {color}]"

    console.print(
        f"  [bold]exit:[/bold] {result.exit_code}  "
        f"[bold]time:[/bold] {result.elapsed_s:.2f}s  "
        f"[bold]verdict:[/bold] {verdict}"
    )
    if result.output_truncated:
        console.print(
            f"  [dim]output truncated — kept first {OUTPUT_CAP_CHARS:,} of "
            f"{len(result.stdout) + OUTPUT_CAP_CHARS:,}+ chars[/dim]"
        )
    if result.stdout.strip():
        preview = result.stdout.strip()[:200]
        console.print(f"  [dim]stdout preview:[/dim] {preview!r}")
    console.print()


def _pct_bar(count: int, total: int, width: int = 20) -> Text:
    """Returns a rich Text bar of X's and dots scaled to the hit percentage.

    Green when count is 0 (clean), yellow for minority, red for majority.
    Safe when total is 0 — renders a fully-empty bar.
    """
    pct = count / total if total > 0 else 0
    filled = round(pct * width)
    bar_str = "X" * filled + "." * (width - filled)
    color = "green" if count == 0 else ("yellow" if pct < 0.5 else "red")
    return Text(f"{bar_str}  ({int(pct * 100)}%)", style=color)


def print_final_stats(stats: dict[str, int], total: int) -> None:
    """Renders the aggregate limit-hit statistics as a rich Table under a yellow Rule.

    Each row shows absolute hit count, percentage, and a visual bar.
    A totals row is appended after a section separator.
    """
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Sandbox Execution Limit Statistics", show_lines=True)
    table.add_column("Limit", style="bold", min_width=24)
    table.add_column("Hits", justify="center")
    table.add_column("Percentage", justify="center")
    table.add_column("Bar", min_width=26)

    row_colors = {
        "Clean (no limit hit)": "green",
        f"Timeout  ({TIMEOUT_SECONDS}s)": "red",
        f"Memory   ({MEMORY_LIMIT_MB} MB)": "red",
        f"Output   ({OUTPUT_CAP_CHARS:,} chars)": "yellow",
        "Error": "dim",
    }

    for label, count in stats.items():
        color = row_colors.get(label, "white")
        pct_str = f"{count / total * 100:.1f}%" if total > 0 else "—"
        table.add_row(
            f"[{color}]{label}[/{color}]",
            str(count),
            pct_str,
            _pct_bar(count, total),
        )

    table.add_section()
    table.add_row("[bold]Total runs[/bold]", f"[bold]{total}[/bold]", "", "")

    console.print(table)
    console.print()


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Orchestrates the full demo: configure Gemini, loop through scenarios, print stats.

    For each scenario, calls generate_code() then execute_in_sandbox(), accumulates
    limit-hit counts, and finally delegates to print_final_stats().
    """
    console.print(
        Panel.fit(
            "[bold yellow]Docker Sandbox Execution Monitor[/bold yellow]\n"
            "[dim]Gemini generates code snippets; each runs in an isolated Docker container.[/dim]\n"
            f"[dim]{len(SCENARIOS)} scenarios  ·  "
            f"{TIMEOUT_SECONDS}s timeout  ·  "
            f"{MEMORY_LIMIT_MB} MB memory  ·  "
            f"{OUTPUT_CAP_CHARS:,} char output cap[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    model = configure_gemini()

    stats: dict[str, int] = {
        "Clean (no limit hit)": 0,
        f"Timeout  ({TIMEOUT_SECONDS}s)": 0,
        f"Memory   ({MEMORY_LIMIT_MB} MB)": 0,
        f"Output   ({OUTPUT_CAP_CHARS:,} chars)": 0,
        "Error": 0,
    }
    total = 0

    for scenario in SCENARIOS:
        console.print(Rule(f"[bold]{scenario['name']}[/bold]", style="white"))
        console.print()

        code = generate_code(model, scenario["prompt"])
        result = execute_in_sandbox(code)
        print_execution_result(result)

        total += 1
        match result.limit_hit:
            case LimitHit.NONE:
                stats["Clean (no limit hit)"] += 1
            case LimitHit.TIMEOUT:
                stats[f"Timeout  ({TIMEOUT_SECONDS}s)"] += 1
            case LimitHit.MEMORY:
                stats[f"Memory   ({MEMORY_LIMIT_MB} MB)"] += 1
            case LimitHit.OUTPUT:
                stats[f"Output   ({OUTPUT_CAP_CHARS:,} chars)"] += 1
            case LimitHit.ERROR:
                stats["Error"] += 1

    print_final_stats(stats, total)


if __name__ == "__main__":
    main()
