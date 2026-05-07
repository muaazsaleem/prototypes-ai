#!/usr/bin/env python3
"""
Edit-Verify Loop Agent

Demonstrates an autonomous code-repair agent that fixes a buggy Python source
file by iteratively prompting Gemini for edits and verifying them with pytest.
Three phases per iteration: read files, generate edit, run tests.
"""

import os
import re
import subprocess
import textwrap
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

MODEL = "gemini-2.5-flash"
MAX_ITERATIONS = 5
SOURCE_FILE = "sample_source.py"
TEST_FILE = "sample_test.py"

SYSTEM_PROMPT = """You are a code repair agent. Fix a Python source file so its failing tests pass.

Rules:
1. Return ONLY the complete fixed Python source file, wrapped in a ```python code block.
2. Fix as many failing tests as you can in one pass.
3. Keep all existing function signatures unchanged.
4. Do not modify or reference the test file."""


# ── Test runner ───────────────────────────────────────────────────────────────


def parse_test_results(output: str) -> dict:
    """Parse pytest stdout to extract pass / fail / error counts.

    Matches the summary line printed by pytest (e.g. '3 passed, 2 failed').
    Returns zeros for any count not present, which happens when pytest exits
    before running tests (e.g. an import error).
    """
    passed = failed = errors = 0
    if m := re.search(r"(\d+) passed", output):
        passed = int(m.group(1))
    if m := re.search(r"(\d+) failed", output):
        failed = int(m.group(1))
    if m := re.search(r"(\d+) error", output):
        errors = int(m.group(1))
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
    }


def run_tests(test_file: str) -> dict:
    """Run pytest on test_file and return counts plus the raw terminal output.

    Captures both stdout and stderr so that import errors (which go to stderr)
    are included in the output dict and can be fed back to the model.
    """
    result = subprocess.run(
        ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return {
        "output": output,
        "returncode": result.returncode,
        **parse_test_results(output),
    }


# ── Code extraction ───────────────────────────────────────────────────────────


def extract_code_block(text: str) -> str | None:
    """Extract the first Python fenced code block from a markdown string.

    Tries ```python first, then a plain ``` block as a fallback.
    Returns the code without the fence markers, or None if nothing matched.
    """
    match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback for models that omit the language tag
    match = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    return match.group(1).strip() if match else None


# ── Display helpers ───────────────────────────────────────────────────────────


def display_model_input(system_prompt: str, user_message: str):
    """Render the outgoing prompt as a styled two-part panel before sending it."""
    elements = []

    # System section — dim to signal it's a meta-instruction, not dialogue
    sys_wrapped = textwrap.fill(system_prompt, width=82, subsequent_indent="        ")
    elements.append(Text.assemble(("SYSTEM: ", "dim"), (sys_wrapped, "dim")))
    elements.append(Rule(style="bright_black"))

    indent = " " * len("USER: ")
    user_wrapped = textwrap.fill(user_message, width=82, subsequent_indent=indent)
    elements.append(Text.assemble(("USER: ", "bold blue"), (user_wrapped, "blue")))

    console.print(
        Panel(
            Group(*elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_model_output(response_text: str):
    """Render the raw LLM response inside a styled assistant panel."""
    indent = " " * len("ASSISTANT: ")
    wrapped = textwrap.fill(response_text, width=82, subsequent_indent=indent)
    content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))
    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def display_test_snapshot(label: str, results: dict, prev: dict | None = None):
    """Print a single-line test result with an optional delta vs. the previous run.

    Green/red delta values make regression vs. improvement immediately visible.
    """
    passed = results["passed"]
    failed = results["failed"]
    total = results["total"]

    pass_str = f"[green]{passed} passed[/green]"
    fail_str = (
        f"[red]{failed} failed[/red]" if failed > 0 else f"[dim]{failed} failed[/dim]"
    )

    delta_str = ""
    if prev is not None:
        dp = results["passed"] - prev["passed"]
        df = results["failed"] - prev["failed"]
        # Positive delta on passed is good; negative delta on failed is good
        delta_p = (
            f"[green]+{dp}[/green]"
            if dp > 0
            else (f"[red]{dp}[/red]" if dp < 0 else "[dim]+/-0[/dim]")
        )
        delta_f = (
            f"[green]{df}[/green]"
            if df < 0
            else (f"[red]+{df}[/red]" if df > 0 else "[dim]+/-0[/dim]")
        )
        delta_str = f"  [dim]Δ passed={delta_p} failed={delta_f}[/dim]"

    console.print(
        f"  [bold]{label}[/bold]  {pass_str}  {fail_str}  [dim]/ {total} total[/dim]{delta_str}"
    )
    console.print()


def display_edit_log_table(edit_log: list):
    """Print the full iteration-by-iteration edit log as a bordered summary table."""
    table = Table(title="Edit Log", show_lines=True)
    table.add_column("Iter", justify="center", style="bold")
    table.add_column("Passed", justify="center")
    table.add_column("Failed", justify="center")
    table.add_column("Δ Passed", justify="center")
    table.add_column("Δ Failed", justify="center")
    table.add_column("Status", justify="center")

    for entry in edit_log:
        dp = entry["delta_passed"]
        df = entry["delta_failed"]
        curr = entry["curr"]

        delta_p = (
            f"[green]+{dp}[/green]"
            if dp > 0
            else (f"[red]{dp}[/red]" if dp < 0 else "[dim]0[/dim]")
        )
        # Fewer failures is an improvement, so negative df is green
        delta_f = (
            f"[green]{df}[/green]"
            if df < 0
            else (f"[red]+{df}[/red]" if df > 0 else "[dim]0[/dim]")
        )

        if curr["failed"] == 0 and curr["errors"] == 0:
            status = "[bold green]ALL PASS[/bold green]"
        elif dp > 0:
            status = "[yellow]improving[/yellow]"
        elif dp == 0 and df == 0:
            status = "[dim]no change[/dim]"
        else:
            status = "[red]regressed[/red]"

        table.add_row(
            str(entry["iteration"]),
            str(curr["passed"]),
            str(curr["failed"]),
            delta_p,
            delta_f,
            status,
        )

    console.print(table)
    console.print()


# ── Agent phases ──────────────────────────────────────────────────────────────


def generate_edit(
    client: genai.Client,
    source_content: str,
    test_content: str,
    test_output: str,
    iteration: int,
) -> str | None:
    """Phase 2: prompt Gemini to produce a fixed version of the source file.

    Sends the current source, the test file, and the latest pytest output so
    the model can see exactly which assertions are failing and why.
    Returns the extracted Python source string, or None if no code block was found.
    """
    user_message = (
        f"Source file ({SOURCE_FILE}):\n"
        f"```python\n{source_content}\n```\n\n"
        f"Test file ({TEST_FILE}):\n"
        f"```python\n{test_content}\n```\n\n"
        f"Test output (iteration {iteration}):\n"
        f"```\n{test_output.strip()}\n```\n\n"
        "Fix the source file so the failing tests pass. Return the complete fixed file."
    )

    display_model_input(SYSTEM_PROMPT, user_message)

    response = client.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    response_text = response.text
    display_model_output(response_text)

    return extract_code_block(response_text)


# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    """Run the edit-verify loop: read → edit → verify, up to MAX_ITERATIONS times."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    source_path = Path(SOURCE_FILE)
    test_path = Path(TEST_FILE)

    if not source_path.exists() or not test_path.exists():
        console.print(
            f"[bold red]Error:[/bold red] {SOURCE_FILE} or {TEST_FILE} not found in the current directory."
        )
        raise SystemExit(1)

    # ── Opening banner ────────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold yellow]Edit-Verify Loop Agent[/bold yellow]\n"
            "[dim]Read failing tests → generate edit → verify → repeat[/dim]\n"
            f"[dim]Model: {MODEL} | Max iterations: {MAX_ITERATIONS}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # ── Phase 1: initial test run ─────────────────────────────────────────────
    console.print(Rule("[bold]Phase 1 — Initial Test Run[/bold]", style="white"))
    console.print()
    initial_results = run_tests(TEST_FILE)
    display_test_snapshot("Before any edits:", initial_results)

    if initial_results["failed"] == 0 and initial_results["errors"] == 0:
        console.print(
            "[bold green]All tests already pass. Nothing to fix.[/bold green]"
        )
        return

    prev_results = initial_results
    edit_log = []

    # ── Main agent loop ───────────────────────────────────────────────────────
    for i in range(1, MAX_ITERATIONS + 1):
        console.print(
            Rule(f"[bold]Iteration {i} / {MAX_ITERATIONS}[/bold]", style="white")
        )
        console.print()

        # Phase 2: generate edit
        console.print(
            "[bold cyan]-- Phase 2: Generate Edit ----------------------------[/bold cyan]"
        )
        console.print()

        source_content = source_path.read_text()
        test_content = test_path.read_text()

        new_source = generate_edit(
            client, source_content, test_content, prev_results["output"], i
        )

        if new_source is None:
            console.print(
                "[bold red]Error:[/bold red] No code block in model response. Stopping."
            )
            break

        # Overwrite the source file with the model's proposed fix
        source_path.write_text(new_source)
        console.print(f"  [dim]Edit applied → {SOURCE_FILE}[/dim]")
        console.print()

        # Phase 3: verify
        console.print(
            "[bold cyan]-- Phase 3: Verify -----------------------------------[/bold cyan]"
        )
        console.print()

        curr_results = run_tests(TEST_FILE)

        delta_passed = curr_results["passed"] - prev_results["passed"]
        delta_failed = curr_results["failed"] - prev_results["failed"]

        edit_log.append(
            {
                "iteration": i,
                "prev": prev_results,
                "curr": curr_results,
                "delta_passed": delta_passed,
                "delta_failed": delta_failed,
            }
        )

        display_test_snapshot(f"After iteration {i}:", curr_results, prev_results)

        prev_results = curr_results

        # Stop early once all tests pass
        if curr_results["failed"] == 0 and curr_results["errors"] == 0:
            console.print(
                "  [bold green]All tests pass — agent succeeded early.[/bold green]"
            )
            console.print()
            break

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Summary[/bold yellow]", style="yellow"))
    console.print()

    display_edit_log_table(edit_log)

    final = prev_results
    tests_fixed = final["passed"] - initial_results["passed"]

    console.print(
        f"  [bold]Initial:[/bold]  {initial_results['passed']} passed / {initial_results['failed']} failed"
    )
    console.print(
        f"  [bold]Final:  [/bold]  {final['passed']} passed / {final['failed']} failed"
    )
    console.print(
        f"  [bold]Fixed:  [/bold]  {tests_fixed} additional test(s) now passing"
    )
    console.print()

    if final["failed"] == 0 and final["errors"] == 0:
        console.print(
            "  [bold green]VERDICT: All tests pass — full success.[/bold green]"
        )
    elif tests_fixed > 0:
        console.print(
            f"  [bold yellow]VERDICT: Partial success — {tests_fixed} test(s) fixed, {final['failed']} remaining.[/bold yellow]"
        )
    else:
        console.print(
            "  [bold red]VERDICT: No improvement — agent could not fix the source.[/bold red]"
        )
    console.print()


if __name__ == "__main__":
    main()
