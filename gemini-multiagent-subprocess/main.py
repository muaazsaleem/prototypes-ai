#!/usr/bin/env python3
"""
Gemini Multi-Agent via Python subprocess
=========================================
Demonstrates what a multi-agent orchestrator looks like WITHOUT a framework.

Every concept here is something an agent SDK (LangGraph, CrewAI, AutoGen, etc.)
abstracts for you. Here we do it all by hand so the mechanics are visible:

  1. PLANNING        — orchestrator calls Gemini to decompose a task into subtasks
  2. SPAWNING        — each subtask becomes a subprocess (the "agent")
  3. MESSAGE PASSING — tasks sent over stdin, results read from stdout (JSON lines)
  4. LIFECYCLE TRACKING — polling loop with process.poll() to detect completion
  5. TIMEOUT / ERROR — per-agent deadline; failed agents don't block the rest
  6. AGGREGATION     — collect all results, pass back to Gemini for synthesis

Model: gemini-2.5-flash
SDK:   google-genai  (raw — no agent framework on top)
"""

import json
import os
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

MODEL = "gemini-2.5-flash"
SUBAGENT_TIMEOUT_SECS = 60      # kill a subprocess if it takes too long
POLL_INTERVAL_SECS   = 0.3      # how often to check process.poll()
TOPIC = "How LLMs are changing software engineering in 2025"

SUBAGENT_SCRIPT = Path(__file__).parent / "subagent.py"


# ── Agent lifecycle state machine ─────────────────────────────────────────────
# This is what frameworks like LangGraph encode in their graph state.
# We do it manually with a simple enum + dataclass.

class AgentStatus(Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    TIMEOUT  = "timeout"


@dataclass
class AgentHandle:
    """Everything the orchestrator needs to track one running sub-agent."""
    agent_id:   str
    task:       str
    status:     AgentStatus = AgentStatus.PENDING
    process:    subprocess.Popen | None = None
    started_at: float = 0.0
    result:     str = ""
    error:      str = ""

    # stdout/stderr collected after the process ends
    raw_stdout: str = ""
    raw_stderr: str = ""


# ── Gemini helper ──────────────────────────────────────────────────────────────

def call_gemini(client: genai.Client, prompt: str) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=1200),
    )
    return response.text.strip()


# ── Phase 1: Planning ──────────────────────────────────────────────────────────
# Orchestrator asks Gemini to break the topic into parallel research subtasks.
# An agent SDK would call this "task decomposition" and hide it behind a graph node.

def plan_subtasks(client: genai.Client, topic: str) -> list[str]:
    console.print(Rule("[bold cyan]Phase 1 — Planning (Orchestrator)[/bold cyan]",
                       style="cyan"))

    prompt = (
        f"You are a research planner. Break this topic into exactly 3 focused, "
        f"non-overlapping research subtasks that can be investigated in parallel.\n\n"
        f"Topic: {topic}\n\n"
        f"Return ONLY a JSON array of 3 strings. Each string is a clear, self-contained "
        f"research question or directive. No extra text, just the JSON array."
    )

    console.print(Panel(
        Text.assemble(("USER: ", "bold blue"), (prompt, "blue")),
        title="[bright_black]Orchestrator → Gemini (planning)[/bright_black]",
        border_style="bright_black", padding=(1, 2),
    ))

    raw = call_gemini(client, prompt)

    console.print(Panel(
        Text.assemble(("ASSISTANT: ", "bold green"), (raw, "italic")),
        title="[bright_black]Gemini → Orchestrator[/bright_black]",
        border_style="bright_black", padding=(1, 2),
    ))

    # Strip markdown fences if Gemini wrapped the JSON
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    subtasks: list[str] = json.loads(clean)
    assert len(subtasks) == 3, f"Expected 3 subtasks, got {len(subtasks)}"
    return subtasks


# ── Phase 2: Spawning sub-agents ───────────────────────────────────────────────
# Each sub-agent is a separate Python process running subagent.py.
# The SDK equivalent: agent.run(task) — one line. Here we see the full picture:
#   - subprocess.Popen with pipes
#   - writing JSON to stdin
#   - closing stdin so the child knows input is complete

def spawn_agents(subtasks: list[str]) -> list[AgentHandle]:
    console.print(Rule("[bold cyan]Phase 2 — Spawning Sub-Agents[/bold cyan]",
                       style="cyan"))

    handles: list[AgentHandle] = []

    for i, task in enumerate(subtasks):
        agent_id = f"agent-{i+1}"
        handle = AgentHandle(agent_id=agent_id, task=task)

        task_payload = json.dumps({"agent_id": agent_id, "task": task})

        # ── The part a framework hides: raw subprocess plumbing ───────────────
        proc = subprocess.Popen(
            [sys.executable, str(SUBAGENT_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # sub-agents log to stderr so it shows in terminal
            text=True,
            env=os.environ.copy(),    # pass GEMINI_API_KEY through to the child
        )

        # Send the task and close stdin (signals end-of-input to the child)
        proc.stdin.write(task_payload)
        proc.stdin.close()

        handle.process    = proc
        handle.status     = AgentStatus.RUNNING
        handle.started_at = time.time()
        handles.append(handle)

        console.print(
            f"  [green]spawned[/green] [bold]{agent_id}[/bold] (pid={proc.pid}) "
            f"— task: [dim]{task[:70]}[/dim]"
        )

    return handles


# ── Phase 3: Tracking completion ───────────────────────────────────────────────
# This is the part frameworks make invisible. Without one you must:
#   - poll process.poll() in a loop (returns None if still running)
#   - enforce per-agent timeouts (kill if exceeded)
#   - handle partial failures gracefully so the pipeline continues

def wait_for_all_agents(handles: list[AgentHandle]) -> None:
    console.print(Rule("[bold cyan]Phase 3 — Tracking Sub-Agent Lifecycle[/bold cyan]",
                       style="cyan"))

    console.print(
        "[dim]Polling every "
        f"{POLL_INTERVAL_SECS}s — process.poll() returns None while running, "
        "exit-code when done.[/dim]\n"
    )

    while True:
        still_running = [h for h in handles if h.status == AgentStatus.RUNNING]
        if not still_running:
            break

        for handle in still_running:
            elapsed = time.time() - handle.started_at

            # ── Timeout enforcement ───────────────────────────────────────────
            if elapsed > SUBAGENT_TIMEOUT_SECS:
                handle.process.kill()
                handle.status = AgentStatus.TIMEOUT
                handle.error  = f"killed after {elapsed:.1f}s"
                console.print(
                    f"  [red]TIMEOUT[/red] [bold]{handle.agent_id}[/bold] "
                    f"after {elapsed:.1f}s"
                )
                continue

            # ── poll() is the key primitive: None = still alive ───────────────
            exit_code = handle.process.poll()

            if exit_code is None:
                # Still running — print a heartbeat dot every ~3 seconds
                if int(elapsed * 10) % int(3 / POLL_INTERVAL_SECS) == 0:
                    console.print(
                        f"  [dim]…[/dim] [bold]{handle.agent_id}[/bold] "
                        f"still running ({elapsed:.0f}s elapsed)",
                        end="\r",
                    )
                continue

            # ── Process exited — harvest stdout/stderr ────────────────────────
            handle.raw_stdout = handle.process.stdout.read()
            handle.raw_stderr = handle.process.stderr.read()

            if exit_code == 0:
                try:
                    data = json.loads(handle.raw_stdout)
                    handle.result = data.get("result", "")
                    handle.status = AgentStatus.DONE
                    console.print(
                        f"  [green]DONE[/green]  [bold]{handle.agent_id}[/bold] "
                        f"in {elapsed:.1f}s — {len(handle.result)} chars"
                    )
                except json.JSONDecodeError as exc:
                    handle.status = AgentStatus.FAILED
                    handle.error  = f"bad JSON from stdout: {exc}"
                    console.print(
                        f"  [red]FAIL[/red]  [bold]{handle.agent_id}[/bold] "
                        f"— {handle.error}"
                    )
            else:
                handle.status = AgentStatus.FAILED
                handle.error  = (handle.raw_stderr or "non-zero exit").strip()
                console.print(
                    f"  [red]FAIL[/red]  [bold]{handle.agent_id}[/bold] "
                    f"(exit={exit_code}) — {handle.error[:80]}"
                )

        time.sleep(POLL_INTERVAL_SECS)

    console.print()


# ── Phase 4: Synthesis ─────────────────────────────────────────────────────────
# Orchestrator collects all sub-agent results and calls Gemini once more to
# synthesize them into a final answer. Frameworks call this "reduce" or "join".

def synthesise(client: genai.Client, topic: str,
               handles: list[AgentHandle]) -> str:
    console.print(Rule("[bold cyan]Phase 4 — Synthesis (Orchestrator)[/bold cyan]",
                       style="cyan"))

    research_block = ""
    for h in handles:
        if h.status == AgentStatus.DONE:
            research_block += f"\n### {h.agent_id}: {h.task}\n{h.result}\n"
        else:
            research_block += f"\n### {h.agent_id}: {h.task}\n[FAILED — {h.error}]\n"

    prompt = (
        f"You are a senior technical writer. Synthesize the following parallel "
        f"research findings into a single coherent summary on:\n\n"
        f"Topic: {topic}\n\n"
        f"Research findings:\n{research_block}\n\n"
        f"Write 3-4 tight paragraphs. Do not use section headers."
    )

    console.print(Panel(
        Text.assemble(("USER: ", "bold blue"),
                      (textwrap.fill(prompt, 80), "blue")),
        title="[bright_black]Orchestrator → Gemini (synthesis)[/bright_black]",
        border_style="bright_black", padding=(1, 2),
    ))

    result = call_gemini(client, prompt)

    console.print(Panel(
        Text.assemble(("ASSISTANT: ", "bold green"), (result, "italic")),
        title="[bright_black]Gemini → Orchestrator (final)[/bright_black]",
        border_style="bright_black", padding=(1, 2),
    ))

    return result


# ── Status dashboard ───────────────────────────────────────────────────────────

def print_status_table(handles: list[AgentHandle]) -> None:
    table = Table(title="Sub-Agent Completion Summary", show_lines=True)
    table.add_column("Agent",  style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Result / Error", max_width=60)

    STATUS_STYLE = {
        AgentStatus.DONE:    "[green]DONE[/green]",
        AgentStatus.FAILED:  "[red]FAILED[/red]",
        AgentStatus.TIMEOUT: "[yellow]TIMEOUT[/yellow]",
        AgentStatus.RUNNING: "[blue]RUNNING[/blue]",
        AgentStatus.PENDING: "[dim]PENDING[/dim]",
    }

    for h in handles:
        if h.status == AgentStatus.DONE:
            detail = h.result[:80] + "…" if len(h.result) > 80 else h.result
        else:
            detail = f"[red]{h.error[:80]}[/red]"

        table.add_row(h.agent_id, STATUS_STYLE[h.status], detail)

    console.print(table)
    console.print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    console.print(Panel.fit(
        "[bold yellow]Gemini Multi-Agent — Raw subprocess edition[/bold yellow]\n"
        "[dim]No framework. Every abstraction shown explicitly.[/dim]\n"
        f'[dim]Topic: "{TOPIC}"[/dim]\n\n'
        "[dim]What you'll see that SDKs hide:\n"
        "  • subprocess.Popen()  — spawning agents\n"
        "  • stdin/stdout JSON   — inter-agent messaging\n"
        "  • process.poll()      — lifecycle tracking\n"
        "  • timeout + kill()    — failure handling\n"
        "  • manual aggregation  — collecting results[/dim]",
        border_style="yellow",
    ))
    console.print()

    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    except KeyError:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY not set.")
        raise SystemExit(1)

    # Phase 1 — plan
    subtasks = plan_subtasks(client, TOPIC)

    # Phase 2 — spawn one subprocess per subtask
    console.print()
    handles = spawn_agents(subtasks)

    # Phase 3 — wait for all agents; track lifecycle manually
    console.print()
    wait_for_all_agents(handles)

    # Status table
    print_status_table(handles)

    # Phase 4 — synthesize
    final = synthesise(client, TOPIC, handles)

    console.print(Rule("[bold green]Final Report[/bold green]", style="green"))
    for para in final.split("\n\n"):
        console.print(textwrap.fill(para.strip(), width=88))
        console.print()

    console.print(Rule("[bold yellow]End of Demo[/bold yellow]", style="yellow"))


if __name__ == "__main__":
    main()
