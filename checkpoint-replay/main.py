#!/usr/bin/env python3
"""
Resumable AI Agent
A production-ready template for multi-step AI agents with checkpointing.

This agent automatically:
  1. Detects an existing checkpoint (checkpoint.json).
  2. Resumes from the last completed step.
  3. Saves progress after every successful step.
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
from rich.text import Text

console = Console()

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_NAME = "gemini-2.5-flash"
CHECKPOINT_FILE = "checkpoint.json"

# The multi-step analytical task the agent works through
TASK = "Design a URL shortener service (like bit.ly) for 100 million URLs."

# Sequential steps; each step receives the previous step's output as context.
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

# ── Display Helpers ────────────────────────────────────────────────────────────


def print_llm_interaction(prompt: str, response_text: str) -> None:
    """Prints the LLM input and response in standardized panels."""
    # Model Input block
    input_elements = []
    role = "user"
    label_style = "bold blue"
    content_style = "blue"

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


# ── LLM ───────────────────────────────────────────────────────────────────────

_client: genai.Client | None = None


def get_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Call configure_client() before running the agent.")
    return _client


def configure_client(api_key: str) -> None:
    global _client
    _client = genai.Client(api_key=api_key)


def call_model(prompt: str) -> str:
    response = get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text.strip()


def build_prompt(step_index: int, context: str) -> str:
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
        f"Context from the previous steps:\n{context}\n\n"
        f"{instruction}"
    )


# ── Checkpoint Management ───────────────────────────────────────────────────────


def save_checkpoint(completed_step: int, history: list[dict]) -> None:
    """
    Persists the complete state of the agent.
    
    Captures:
      - Metadata (task, model, timestamp)
      - The full history of prompts and responses for every step.
    """
    data = {
        "metadata": {
            "task": TASK,
            "model": MODEL_NAME,
            "saved_at": datetime.now().isoformat(),
        },
        "state": {
            "last_completed_step": completed_step,
            # history is a list of {"step": i, "step_name": "...", "prompt": "...", "response": "..."}
            "history": history,
        },
    }
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_checkpoint() -> dict | None:
    if not Path(CHECKPOINT_FILE).exists():
        return None
    try:
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def delete_checkpoint() -> None:
    if Path(CHECKPOINT_FILE).exists():
        Path(CHECKPOINT_FILE).unlink()


# ── Agent Loop ────────────────────────────────────────────────────────────────


def run_agent(reset: bool = False) -> None:
    """Main execution loop with automatic resumption and full-state recovery."""
    if reset:
        console.print("[yellow]Resetting agent state...[/yellow]")
        delete_checkpoint()

    checkpoint = load_checkpoint()
    last_done = -1
    history = []

    if checkpoint:
        last_done = checkpoint["state"]["last_completed_step"]
        history = checkpoint["state"]["history"]
        
        console.print(
            Panel.fit(
                "[bold cyan]Resuming Agent (Full State Restored)[/bold cyan]\n"
                f"[dim]Loaded checkpoint from {checkpoint['metadata']['saved_at']}[/dim]\n"
                f"[dim]Resuming from step {last_done + 2} of {len(STEPS)}[/dim]",
                border_style="cyan",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold yellow]Starting Fresh Agent[/bold yellow]\n"
                f"[dim]Task: {TASK}[/dim]\n"
                f"[dim]{len(STEPS)} steps to complete[/dim]",
                border_style="yellow",
            )
        )

    console.print()

    for i, (step_name, _) in enumerate(STEPS):
        # ── Restore phase ─────────────────────────────────────────────────────
        if i <= last_done:
            # We don't just skip; we "replay" the restored knowledge for the user
            console.print(
                f"  [dim]Step {i + 1}: {step_name}  [green]— restored from history[/green][/dim]"
            )
            continue

        # ── Execution phase ───────────────────────────────────────────────────
        console.print(
            Rule(f"[bold]Step {i + 1}/{len(STEPS)}: {step_name}[/bold]", style="white")
        )
        console.print()

        # Build context from the entire history of previous responses
        cumulative_context = "\n\n".join(
            [f"--- Result from Step {h['step'] + 1} ({STEPS[h['step']][0]}) ---\n{h['response']}" 
             for h in history]
        )
        
        prompt = build_prompt(i, cumulative_context)
        
        # In a real scenario, this might fail (network, API limit, etc.)
        response_text = call_model(prompt)
        
        # Record everything about this step
        step_record = {
            "step": i,
            "step_name": step_name,
            "prompt": prompt,
            "response": response_text,
        }
        history.append(step_record)

        # Critical: Save EVERYTHING immediately
        save_checkpoint(i, history)

        print_llm_interaction(prompt, response_text)
        console.print(f"  [green]✓ State & history saved[/green]")
        console.print()

    console.print(Rule(style="green"))
    console.print("[bold green]✓ Task completed successfully.[/bold green]")
    console.print()


# ── Entry Point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable AI Agent with Checkpointing",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing checkpoint and start from scratch",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        sys.exit(1)

    configure_client(api_key)
    
    try:
        run_agent(reset=args.reset)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Progress is saved.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error occurred:[/bold red] {e}")
        console.print("[yellow]You can resume by running the script again.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
