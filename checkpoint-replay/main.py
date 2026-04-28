#!/usr/bin/env python3
"""
Checkpoint and Replay
Demonstrates idempotency and checkpointing in multi-step AI agents.

Run modes:
  run            → Start fresh WITH checkpointing; crashes mid-run to show the value
  resume         → Recover from the saved checkpoint; skips already-completed steps
  no-checkpoint  → Same task without checkpointing; crash + forced restart shows the waste
"""

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Display Helpers ────────────────────────────────────────────────────────────


def print_llm_interaction(prompt: str, response_text: str) -> None:
    """Prints the LLM input and response in standardized grey panels.

    Args:
        prompt: The user input string sent to the model.
        response_text: The assistant's response string.

    Side effects:
        Prints formatted output to the terminal using rich.
    """
    # Model Input block
    input_elements = []
    role = "user"
    label_style = "bold blue"
    content_style = "blue"

    # Indent content after the persona label
    indent = " " * (len(role) + 2)
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent=indent)

    input_elements.append(
        Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
    )

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    # Model Response block
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
    )

    console.print(
        Panel(
            response_content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_NAME = "gemini-2.0-flash"
CHECKPOINT_FILE = "checkpoint.json"

# The agent will complete this many steps successfully, then simulate a crash.
# Steps are 0-indexed, so KILL_AT_STEP=3 means steps 0, 1, 2 succeed and step 3 triggers the crash.
KILL_AT_STEP = 3

# The multi-step analytical task the agent works through
TASK = "Design a URL shortener service (like bit.ly) for 100 million URLs."

# Six sequential steps; each step receives the previous step's output as context.
# This dependency chain is what makes checkpointing valuable — losing step N means
# losing all the structured context that was built up to reach step N.
STEPS = [
    (
        "Requirements Analysis",
        "List 4 functional and 4 non-functional requirements. One line each.",
    ),
    (
        "Core Components",
        "Based on the requirements above, list 5 core system components with one-line descriptions.",
    ),
    (
        "Data Model",
        "Based on the components above, design a minimal data model: 2-3 tables with fields and types.",
    ),
    (
        "API Endpoints",
        "Based on the data model above, define 4 core REST endpoints: METHOD /path → purpose.",
    ),
    (
        "Bottlenecks & Mitigations",
        "Based on the API design above, list 3 key bottlenecks and a one-line mitigation for each.",
    ),
    (
        "Executive Summary",
        "Based on all the above, write a 4-5 sentence executive summary of the complete design.",
    ),
]

# ── LLM ───────────────────────────────────────────────────────────────────────

# Module-level client; configured once in main() and reused by all steps
_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Returns the shared Gemini client, raising if not yet configured.

    Returns:
        The initialized genai.Client instance.

    Raises:
        RuntimeError: If configure_client() has not been called.
    """
    if _client is None:
        raise RuntimeError("Call configure_client() before running the agent.")
    return _client


def configure_client(api_key: str) -> None:
    """Initializes the Gemini client with the given API key.

    Args:
        api_key: The Google API key for Gemini.

    Side effects:
        Mutates the global _client variable.
    """
    global _client
    _client = genai.Client(api_key=api_key)


def call_model(prompt: str) -> str:
    """Sends a single prompt to Gemini and returns the response text.

    Args:
        prompt: The input text to send to the model.

    Returns:
        The stripped text response from the model.

    Side effects:
        Makes a network call to the Gemini API.
    """
    response = get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text.strip()


def build_prompt(step_index: int, prev_output: str) -> str:
    """Constructs the LLM prompt for a given step.

    Step 0 uses only the task description; every subsequent step appends the
    previous step's output so the model can build on prior analysis.

    Args:
        step_index: The 0-based index of the current step.
        prev_output: The text output from the previous step (if any).

    Returns:
        A formatted prompt string containing task, context, and instruction.
    """
    _, instruction = STEPS[step_index]
    if step_index == 0:
        return (
            f"You are a senior software architect.\n"
            f"Task: {TASK}\n\n"
            f"{instruction}"
        )
    return (
        f"You are a senior software architect.\n"
        f"Task: {TASK}\n\n"
        f"Context from the previous step:\n{prev_output}\n\n"
        f"{instruction}"
    )


# ── Checkpoint I/O ─────────────────────────────────────────────────────────────


def save_checkpoint(completed_step: int, outputs: dict[int, str]) -> None:
    """Persists the agent's current state to disk immediately after a step completes.

    The invariant is: checkpoint always reflects a fully consistent state —
    every step listed in it is genuinely done. This makes resumption safe.

    Args:
        completed_step: The index of the last successfully completed step.
        outputs: A dictionary mapping step indices to their respective output text.

    Side effects:
        Writes a JSON file (checkpoint.json) to the current directory.
    """
    data = {
        "last_completed_step": completed_step,
        "saved_at": datetime.now().isoformat(),
        "task": TASK,
        # JSON keys must be strings; convert int keys to str here
        "outputs": {str(k): v for k, v in outputs.items()},
    }
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_checkpoint() -> dict | None:
    """Reads the checkpoint from disk.

    Returns:
        The checkpoint data as a dictionary, or None if no file exists.

    Side effects:
        Reads from checkpoint.json if it exists.
    """
    if not Path(CHECKPOINT_FILE).exists():
        return None
    with open(CHECKPOINT_FILE) as f:
        return json.load(f)


def delete_checkpoint() -> None:
    """Removes any existing checkpoint file from the filesystem.

    Side effects:
        Deletes checkpoint.json if it exists.
    """
    if Path(CHECKPOINT_FILE).exists():
        Path(CHECKPOINT_FILE).unlink()


# ── Mode: run ─────────────────────────────────────────────────────────────────


def run_with_checkpoint() -> None:
    """Starts a fresh agent run with checkpointing enabled.

    The agent saves a checkpoint after every step, then intentionally crashes
    at KILL_AT_STEP so the user can see what gets preserved.
    Run `python main.py resume` after this to observe the recovery.

    Side effects:
        Deletes old checkpoints, makes API calls, writes new checkpoints,
        and eventually exits the process with code 1.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Checkpoint & Replay: Multi-Step Agent[/bold yellow]\n"
            "[dim]Mode: WITH CHECKPOINTING[/dim]\n"
            f"[dim]{len(STEPS)} steps  ·  Simulated crash after step {KILL_AT_STEP}  ·  Run `resume` to recover[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Wipe any stale checkpoint so this run starts clean
    delete_checkpoint()

    outputs: dict[int, str] = {}

    for i, (step_name, _) in enumerate(STEPS):

        # ── Simulate crash before running this step ────────────────────────
        if i == KILL_AT_STEP:
            console.print()
            console.print(Rule("[bold red]SIMULATED CRASH[/bold red]", style="red"))
            console.print()
            console.print(
                f"  [red]Process killed at step {i + 1}. "
                f"({i} of {len(STEPS)} steps completed.)[/red]"
            )
            console.print(
                f"  [green]Checkpoint saved through step {i}: "
                f'"{STEPS[i - 1][0]}"[/green]'
            )
            console.print()
            console.print(
                "  [bold]→ Run:[/bold] [cyan]python main.py resume[/cyan]"
                "  [dim]to recover and continue[/dim]"
            )
            console.print()
            # Exit with error code to make the crash feel real
            sys.exit(1)

        # ── Run this step ──────────────────────────────────────────────────
        console.print(
            Rule(f"[bold]Step {i + 1}/{len(STEPS)}: {step_name}[/bold]", style="white")
        )
        console.print()

        prev_output = outputs.get(i - 1, "")
        prompt = build_prompt(i, prev_output)
        output = call_model(prompt)
        outputs[i] = output

        # Write checkpoint immediately after the step succeeds.
        # If the agent crashes on the NEXT step, this step's output is safe.
        save_checkpoint(i, outputs)

        print_llm_interaction(prompt, output)

        console.print(
            f"  [green]✓ Checkpoint saved  [dim](step {i + 1} of {len(STEPS)})[/dim][/green]"
        )
        console.print()


# ── Mode: resume ──────────────────────────────────────────────────────────────


def resume_from_checkpoint() -> None:
    """Resumes an agent run from the last saved checkpoint.

    Loads the checkpoint written by `run` mode and continues from the next unfinished step.
    Steps already present in the checkpoint are skipped entirely — no repeated LLM calls.

    Side effects:
        Reads checkpoints, makes API calls, writes new checkpoints.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Checkpoint & Replay: Resuming from Checkpoint[/bold yellow]\n"
            "[dim]Mode: RESUME  ·  Loading saved progress — skipping completed steps[/dim]\n"
            f"[dim]Total steps: {len(STEPS)}  ·  Resuming from unfinished work[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    checkpoint = load_checkpoint()
    if checkpoint is None:
        console.print(
            "[bold red]Error:[/bold red] No checkpoint found. "
            "Run [cyan]python main.py run[/cyan] first."
        )
        sys.exit(1)

    last_done: int = checkpoint["last_completed_step"]
    saved_at: str = checkpoint["saved_at"]
    # Restore step outputs from the checkpoint; keys were serialized as strings
    outputs: dict[int, str] = {int(k): v for k, v in checkpoint["outputs"].items()}

    # ── Show which steps are already done vs. still pending ───────────────────
    console.print(Rule("[bold cyan]Checkpoint State[/bold cyan]", style="cyan"))
    console.print()

    state_table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    state_table.add_column("#", style="bold", min_width=3)
    state_table.add_column("Step Name", min_width=28)
    state_table.add_column("Status", justify="center", min_width=26)

    for i, (step_name, _) in enumerate(STEPS):
        if i <= last_done:
            status = "[green]✓ restored from checkpoint[/green]"
        elif i == last_done + 1:
            status = "[cyan]→ resuming here[/cyan]"
        else:
            status = "[dim]pending[/dim]"
        state_table.add_row(str(i + 1), step_name, status)

    console.print(state_table)
    console.print()
    console.print(f"  [dim]Checkpoint saved at: {saved_at}[/dim]")
    console.print()

    # ── Execute only the remaining steps ──────────────────────────────────────
    steps_skipped = 0
    steps_executed = 0

    for i, (step_name, _) in enumerate(STEPS):

        if i <= last_done:
            # This step is already in the checkpoint; skip it entirely
            console.print(
                f"  [dim]Step {i + 1}: {step_name}  "
                f"[green]— skipped (checkpoint)[/green][/dim]"
            )
            steps_skipped += 1
            continue

        # This step was not completed before the crash; run it now
        console.print()
        console.print(
            Rule(f"[bold]Step {i + 1}/{len(STEPS)}: {step_name}[/bold]", style="white")
        )
        console.print()

        prev_output = outputs.get(i - 1, "")
        prompt = build_prompt(i, prev_output)
        output = call_model(prompt)
        outputs[i] = output
        steps_executed += 1

        print_llm_interaction(prompt, output)

        console.print(f"  [green]✓ Step {i + 1} complete[/green]")

    # ── Recovery summary ───────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold yellow]Recovery Summary[/bold yellow]", style="yellow"))
    console.print()

    summary_table = Table(
        title="[bold yellow]Agent Resumption Metrics[/bold yellow]",
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        show_lines=True,
    )
    summary_table.add_column("Metric", min_width=36)
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total steps in task", str(len(STEPS)))
    summary_table.add_row(
        "Recovered from checkpoint (free)", f"[green]{steps_skipped}[/green]"
    )
    summary_table.add_row(
        "Executed fresh after resume", f"[cyan]{steps_executed}[/cyan]"
    )
    summary_table.add_row(
        "LLM calls avoided", f"[bold green]{steps_skipped}[/bold green]"
    )

    console.print(summary_table)
    console.print()
    console.print(
        "  [bold green]✓ Agent resumed successfully. No work was repeated.[/bold green]"
    )
    console.print()


# ── Mode: no-checkpoint ───────────────────────────────────────────────────────


def run_without_checkpoint() -> None:
    """Runs the same agent task WITHOUT writing any checkpoints.

    After the same simulated crash, there is no state to recover — the agent
    must restart from step 1. This makes the wasted LLM calls explicit.

    Side effects:
        Makes API calls, prints comparison metrics.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Checkpoint & Replay: Without Checkpointing[/bold yellow]\n"
            "[dim]Mode: NO CHECKPOINT  ·  Same crash, no recovery possible[/dim]\n"
            f"[dim]{len(STEPS)} steps  ·  Crash at step {KILL_AT_STEP}  ·  Forced restart from step 1[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    total_calls = 0
    wasted_calls = 0

    # ── Run 1: crashes without saving any state ────────────────────────────────
    console.print(
        Rule(
            "[bold cyan]Run 1: Initial Execution (No Checkpoints Saved)[/bold cyan]",
            style="cyan",
        )
    )
    console.print()

    outputs: dict[int, str] = {}

    for i, (step_name, _) in enumerate(STEPS):

        # Simulated crash — identical to the `run` mode crash point
        if i == KILL_AT_STEP:
            console.print()
            console.print(Rule("[bold red]SIMULATED CRASH[/bold red]", style="red"))
            console.print()
            console.print(
                f"  [red]Process killed. {i} steps completed — [bold]none saved.[/bold][/red]"
            )
            console.print(
                f"  [red]All {i} completed steps are [bold]LOST[/bold].[/red]"
            )
            wasted_calls = i
            break

        console.print(
            Rule(
                f"[bold]Run 1 - Step {i + 1}/{len(STEPS)}: {step_name}[/bold]",
                style="white",
            )
        )
        console.print()

        prev_output = outputs.get(i - 1, "")
        prompt = build_prompt(i, prev_output)
        output = call_model(prompt)
        outputs[i] = output
        total_calls += 1

        print_llm_interaction(prompt, output)

    # ── Run 2: forced restart from step 1 — prior work is gone ────────────────
    console.print()
    console.print(
        Rule(
            "[bold magenta]Run 2: Forced Restart from Step 1 (All Prior Work Lost)[/bold magenta]",
            style="magenta",
        )
    )
    console.print()

    # Prior outputs are gone — there is no checkpoint to restore from
    outputs = {}

    for i, (step_name, _) in enumerate(STEPS):
        # Steps that were already completed before the crash are marked as repeated
        is_repeated = i < wasted_calls
        badge = (
            "[bold yellow](repeated — wasted work)[/bold yellow]"
            if is_repeated
            else "[dim](new)[/dim]"
        )

        console.print(
            Rule(
                f"[bold]Run 2 - Step {i + 1}/{len(STEPS)}: {step_name}[/bold] {badge}",
                style="white",
            )
        )
        console.print()

        prev_output = outputs.get(i - 1, "")
        prompt = build_prompt(i, prev_output)
        output = call_model(prompt)
        outputs[i] = output
        total_calls += 1

        print_llm_interaction(prompt, output)

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Rule("[bold yellow]Cost of No Checkpointing[/bold yellow]", style="yellow")
    )
    console.print()

    minimum_calls = len(STEPS)
    waste_pct = round(wasted_calls * 100 / minimum_calls)

    cost_table = Table(
        title="[bold red]Waste Analysis (No Checkpointing)[/bold red]",
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        show_lines=True,
    )
    cost_table.add_column("Metric", min_width=38)
    cost_table.add_column("Value", justify="right")

    cost_table.add_row("Total LLM calls made", f"[bold]{total_calls}[/bold]")
    cost_table.add_row(
        "Minimum calls needed (ideal run)", f"[green]{minimum_calls}[/green]"
    )
    cost_table.add_row(
        "Wasted calls (repeated after crash)", f"[bold red]{wasted_calls}[/bold red]"
    )
    cost_table.add_row("Overhead", f"[bold red]+{waste_pct}%[/bold red]")

    console.print(cost_table)
    console.print()
    console.print(
        f"  [bold red]{wasted_calls} of {minimum_calls} steps were repeated — "
        f"work that checkpointing would have preserved for free.[/bold red]"
    )
    console.print()


# ── Entry Point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point for the Checkpoint & Replay demonstration script.

    Parses command line arguments, checks for API keys, and routes to the
    appropriate execution mode.

    Side effects:
        Parses CLI args, prints errors if config is missing, executes sub-modes.
    """
    parser = argparse.ArgumentParser(
        description="Checkpoint and Replay: Resilient multi-step AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Modes:
              run            Start fresh WITH checkpointing. Crashes at step 3.
                             Then run `resume` to see recovery in action.
              resume         Load checkpoint, skip completed steps, continue.
              no-checkpoint  Run WITHOUT checkpointing. Same crash + restart = wasted LLM calls.
            """),
    )
    parser.add_argument(
        "mode",
        choices=["run", "resume", "no-checkpoint"],
        help="Execution mode",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        sys.exit(1)

    configure_client(api_key)

    if args.mode == "run":
        run_with_checkpoint()
    elif args.mode == "resume":
        resume_from_checkpoint()
    elif args.mode == "no-checkpoint":
        run_without_checkpoint()


if __name__ == "__main__":
    main()
