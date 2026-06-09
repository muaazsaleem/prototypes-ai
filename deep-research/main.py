#!/usr/bin/env python3
import asyncio
import os
import sys
import time
import textwrap
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize Rich console
console = Console()

# ---------------------------------------------------------------------------
# Data Models for Structured Outputs
# ---------------------------------------------------------------------------

class ResearchSubTask(BaseModel):
    title: str = Field(description="Short, focused title of the sub-task (e.g. 'Theoretical Foundation of X' or 'Recent 2026 breakthroughs in Y')")
    description: str = Field(description="Specific research instructions, key questions to answer, and data points to look for.")
    agent_type: str = Field(description="Must be either 'web_search' (for live facts, dates, news) or 'self_knowledge' (for theoretical concepts, principles, history)")

class ResearchPlan(BaseModel):
    topic: str = Field(description="The core topic being researched")
    subtasks: List[ResearchSubTask] = Field(description="List of 2 to 3 complementary, non-overlapping sub-tasks to research the topic deeply.")


# ---------------------------------------------------------------------------
# Core Multi-Agent Orchestration Functions
# ---------------------------------------------------------------------------

async def generate_plan(client: genai.Client, topic: str) -> Tuple[ResearchPlan, float]:
    """
    Phase 1: Lead Planner Agent analyzes the topic and breaks it down into a structured plan.
    """
    console.print("  [yellow]➔[/yellow] [bold yellow]Lead Planner Agent[/bold yellow] is analyzing the topic and creating a research strategy...")
    start_time = time.time()
    
    system_instruction = (
        "You are the Chief Research Planner. Given a research topic, your job is to break it down into 2 to 3 distinct, highly focused subtasks that can be researched in parallel.\n"
        "For each subtask, determine whether it requires 'web_search' (for latest real-time facts, events, and data) or 'self_knowledge' (for theoretical concepts, fundamental physics/mechanics, history, taxonomy, or logical reasoning).\n"
        "Make sure the subtasks are complementary and do not overlap."
    )
    
    contents = (
        f"Research Topic: {topic}\n"
        "Generate a structured research plan with 2 to 3 distinct sub-tasks."
    )
    
    def call_gemini():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ResearchPlan,
                temperature=0.1,
            )
        )
        
    response = await asyncio.to_thread(call_gemini)
    elapsed = time.time() - start_time
    console.print(f"  [green]✓[/green] [bold yellow]Lead Planner Agent[/bold yellow] completed strategy in [dim]{elapsed:.1f}s[/dim]")
    
    # Parse the response using Pydantic
    plan = ResearchPlan.model_validate_json(response.text)
    return plan, elapsed


async def run_research_task(client: genai.Client, subtask: ResearchSubTask, task_num: int) -> Dict[str, Any]:
    """
    Phase 2: Execution Agent (either Web Search or Concept Specialist) runs the sub-task.
    """
    color = "cyan" if subtask.agent_type == "web_search" else "magenta"
    agent_name = "Web Search Agent" if subtask.agent_type == "web_search" else "Concept Specialist"
    
    console.print(f"  [{color}]➔[/{color}] Launching [bold {color}]{agent_name}[/bold {color}] for Task {task_num}: '[italic]{subtask.title}[/italic]'")
    
    start_time = time.time()
    
    # Configure prompts and tools based on the agent specialization
    if subtask.agent_type == "web_search":
        system_instruction = (
            "You are the Web Search Research Specialist. Your job is to research the following specific subtask using your web search capability.\n"
            "Always conduct high-quality searches to find accurate, up-to-date information, news, statistics, or announcements.\n"
            "Provide a detailed, structured research report with specific citations, facts, and dates."
        )
        tools = [types.Tool(google_search=types.GoogleSearch())]
    else:
        system_instruction = (
            "You are the Theoretical & Conceptual Specialist. Your job is to explain the underlying principles, concepts, mechanics, or historical context of the following subtask.\n"
            "Focus deeply on explaining 'how' and 'why' things work, providing robust conceptual frameworks, math/logic if applicable, and deep educational value.\n"
            "Do not use web search; rely on your extensive pre-trained knowledge to provide a deep, authoritative breakdown."
        )
        tools = None
        
    contents = (
        f"Sub-Task: {subtask.title}\n"
        f"Research Instructions: {subtask.description}\n"
        f"Today's date is Monday, June 8, 2026."
    )
    
    def call_gemini():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=0.2,
            )
        )
        
    response = await asyncio.to_thread(call_gemini)
    elapsed = time.time() - start_time
    
    console.print(f"  [green]✓[/green] [bold {color}]{agent_name}[/bold {color}] completed Task {task_num} in [dim]{elapsed:.1f}s[/dim]")
    return {
        "title": subtask.title,
        "agent_type": subtask.agent_type,
        "content": response.text,
        "elapsed": elapsed
    }


async def run_critic(client: genai.Client, topic: str, subtask_reports: List[Dict[str, Any]]) -> Tuple[str, float]:
    """
    Phase 3: Quality Auditor Critic Agent reviews the combined parallel outputs for conflicts or gaps.
    """
    console.print("  [red]➔[/red] [bold red]Research Critic Agent[/bold red] is conducting a cross-report gap analysis and audit...")
    start_time = time.time()
    
    reports_text = ""
    for i, r in enumerate(subtask_reports):
        agent_label = "WEB_SEARCH_AGENT" if r["agent_type"] == "web_search" else "CONCEPT_SPECIALIST"
        reports_text += f"\n--- Report {i+1}: {r['title']} (by {agent_label}) ---\n{r['content']}\n"
        
    system_instruction = (
        "You are the Research Critic & Quality Auditor.\n"
        "Your job is to read the individual reports produced by the parallel research agents and perform a critical review:\n"
        "1. Inconsistencies or Contradictions: Check if the web search findings and the conceptual explanations conflict or contradict in any way.\n"
        "2. Gaps: Identify any important missing details or connections between the subtasks.\n"
        "3. Critique: Provide constructive feedback on how these separate research pieces can be synthesized into a unified, high-quality master report.\n"
        "Write a clear, structured critique and alignment instructions for the Synthesizer."
    )
    
    contents = (
        f"Original Topic: {topic}\n"
        f"Parallel Reports:\n{reports_text}\n"
        "Conduct your critical audit and provide alignment guidance."
    )
    
    def call_gemini():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            )
        )
        
    response = await asyncio.to_thread(call_gemini)
    elapsed = time.time() - start_time
    console.print(f"  [green]✓[/green] [bold red]Research Critic Agent[/bold red] completed review in [dim]{elapsed:.1f}s[/dim]")
    return response.text, elapsed


async def run_synthesis(client: genai.Client, topic: str, subtask_reports: List[Dict[str, Any]], critique: str) -> Tuple[str, float]:
    """
    Phase 4: Synthesizer Agent compiles the final polished master document.
    """
    console.print("  [green]➔[/green] [bold green]Lead Synthesizer Agent[/bold green] is compiling, refining, and generating the final master report...")
    start_time = time.time()
    
    reports_text = ""
    for i, r in enumerate(subtask_reports):
        reports_text += f"\n--- Section: {r['title']} ---\n{r['content']}\n"
        
    system_instruction = (
        "You are the Lead Editor and Synthesizer.\n"
        "Your job is to take the original topic, the research plan, the individual research reports, and the Critic's alignment critique, and compile them into a definitive, comprehensive, beautifully structured final report.\n"
        "The final report should be in professional Markdown and contain:\n"
        "- A stunning, comprehensive title.\n"
        "- An Executive Summary summarizing the key takeaways.\n"
        "- A detailed section for each subtask, fully integrating the findings.\n"
        "- A 'Critical Analysis & Synthesis' section that addresses the Critic's notes and connects the dots between the subtasks.\n"
        "- A 'Future Outlook' section highlighting what to watch for in the coming years.\n"
        "Ensure the prose is detailed, sophisticated, educational, and complete. Avoid placeholders or summaries of what *would* be written; write the complete, thorough report."
    )
    
    contents = (
        f"Original Topic: {topic}\n"
        f"Research Sections:\n{reports_text}\n"
        f"Critic's Quality Review & Alignment Guide:\n{critique}\n"
        "Compile the final complete, highly detailed Markdown report."
    )
    
    def call_gemini():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )
        )
        
    response = await asyncio.to_thread(call_gemini)
    elapsed = time.time() - start_time
    console.print(f"  [green]✓[/green] [bold green]Lead Synthesizer Agent[/bold green] completed master compilation in [dim]{elapsed:.1f}s[/dim]")
    return response.text, elapsed


# ---------------------------------------------------------------------------
# Educational UI Helpers (Rich Terminal Output)
# ---------------------------------------------------------------------------

def display_header():
    """Prints the gorgeous main header panel."""
    console.print(
        Panel.fit(
            "[bold yellow]MULTI-AGENT DEEP RESEARCH ENGINE[/bold yellow]\n"
            "[dim]A pedagogical prototype demonstrating parallel execution, hand-offs, and synthesis.[/dim]\n"
            "[dim]Model: gemini-2.5-flash | Parallel Workers: 2-3 | Handoffs: Planner ➜ Parallel Workers ➜ Critic ➜ Synthesizer[/dim]",
            border_style="yellow",
        )
    )
    console.print()


def display_orchestration_flow():
    """Renders the ASCII Flowchart showing the Agent Orchestration Pattern."""
    flow_text = (
        "                [bold yellow]┌─────────────────────────┐[/bold yellow]\n"
        "                [bold yellow]│   Lead Planner Agent    │[/bold yellow]  (Generates structured Research Plan)\n"
        "                [bold yellow]└────────────┬────────────┘[/bold yellow]\n"
        "                             │  [dim]Split & Dispatch (Parallelism)[/dim]\n"
        "              ┌──────────────┴──────────────┐\n"
        "              ▼                             ▼\n"
        "    [bold cyan]┌───────────────────┐[/bold cyan]         [bold magenta]┌───────────────────┐[/bold magenta]\n"
        "    [bold cyan]│ Web Search Agent  │[/bold cyan]         [bold magenta]│ Concept Specialist│[/bold magenta]  (Executes in parallel)\n"
        "    [bold cyan]│ (Google Grounded) │[/bold cyan]         [bold magenta]│ (Internal Brain)  │[/bold magenta]\n"
        "    [bold cyan]└─────────┬─────────┘[/bold cyan]         [bold magenta]└─────────┬─────────┘[/bold magenta]\n"
        "              │                             │\n"
        "              └──────────────┬──────────────┘\n"
        "                             ▼  [dim]Wait & Synchronize (Handoff)[/dim]\n"
        "                [bold red]┌─────────────────────────┐[/bold red]\n"
        "                [bold red]│  Research Critic Agent  │[/bold red]  (Finds gaps & alignment issues)\n"
        "                [bold red]└────────────┬────────────┘[/bold red]\n"
        "                             │  [dim]Audit Feedback Handoff[/dim]\n"
        "                [bold green]┌─────────────────────────┐[/bold green]\n"
        "                [bold green]│ Lead Synthesizer Agent  │[/bold green]  (Generates final master markdown)\n"
        "                [bold green]└─────────────────────────┘[/bold green]"
    )
    console.print(
        Panel(
            flow_text,
            title="[bold bright_black]Architecture Pattern: Fork-Join Multi-Agent Pipeline[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2)
        )
    )
    console.print()


def print_chat_block(agent_name: str, prompt: str, response: str, color_theme: str = "bright_black"):
    """Displays prompt and model response inside a grey 'chat box' block."""
    input_elements = [
        Text.assemble(("ROLE: ", "bold blue"), (f"{agent_name.upper()}\n", "blue")),
        Text.assemble(("PROMPT SENT: ", "bold blue"), (textwrap.fill(prompt, width=82, subsequent_indent="             "), "blue"))
    ]
    console.print(
        Panel(
            Group(*input_elements),
            title=f"[bold {color_theme}]Agent Input Envelope[/bold {color_theme}]",
            border_style=color_theme,
            padding=(1, 2),
        )
    )
    
    wrapped_response = textwrap.fill(response, width=82, subsequent_indent="           ")
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic")
    )
    console.print(
        Panel(
            response_content,
            title=f"[bold {color_theme}]Agent Output Envelope[/bold {color_theme}]",
            border_style=color_theme,
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Main Orchestrator Loop
# ---------------------------------------------------------------------------

async def main():
    display_header()
    
    # 1. Verification of credentials
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]Error:[/bold red] The GEMINI_API_KEY environment variable is not set.")
        console.print("[dim]Please export your API key before running: export GEMINI_API_KEY='your-key'[/dim]")
        sys.exit(1)
        
    client = genai.Client()
    
    # 2. Get Topic from user or arguments
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = console.input("[bold yellow]Enter research topic: [/bold yellow]").strip()
        if not topic:
            topic = "The current state of room-temperature superconductors in 2026"
            console.print(f"[dim]No topic entered. Defaulting to: '{topic}'[/dim]")
            
    console.print(f"\n[bold green]Starting deep research pipeline for:[/bold green] [bold white]{topic}[/bold white]\n")
    
    # Render the architecture flow to teach the concept
    display_orchestration_flow()
    
    time_tracker = {}
    total_start = time.time()
    
    # =======================================================================
    # PHASE 1: PLANNING
    # =======================================================================
    console.print(Rule("[bold]Phase 1: Multi-Agent Research Planning[/bold]", style="white"))
    console.print("[dim]Concept: One Lead Planner analyzes the broad topic and creates a structured, structured research blueprint.[/dim]\n")
    
    try:
        plan, p_time = await generate_plan(client, topic)
        time_tracker["Phase 1: Planning"] = p_time
    except Exception as e:
        console.print(f"[bold red]Error in Planner Agent:[/bold red] {e}")
        sys.exit(1)
        
    # Render Plan Table
    table = Table(title="Generated Multi-Agent Research Plan", show_lines=True)
    table.add_column("Task ID", justify="center", style="bold", width=8)
    table.add_column("Sub-Task Title", style="cyan", min_width=24)
    table.add_column("Assigned Agent", style="bold")
    table.add_column("Description / Focus Area", style="dim")
    
    for i, task in enumerate(plan.subtasks):
        agent_label = "[bold cyan]Web Search Worker[/bold cyan]\n[dim](Google Grounded)[/dim]" if task.agent_type == "web_search" else "[bold magenta]Concept Specialist[/bold magenta]\n[dim](Self-Knowledge)[/dim]"
        table.add_row(f"0{i+1}", task.title, agent_label, task.description)
        
    console.print(table)
    console.print()
    
    # =======================================================================
    # PHASE 2: PARALLEL EXECUTION (FORK)
    # =======================================================================
    console.print(Rule("[bold]Phase 2: Parallel Execution (The Fork)[/bold]", style="white"))
    console.print("[dim]Concept: Independent tasks are executed concurrently in separate threads/tasks. No agent blocks another.[/dim]\n")
    
    exec_start = time.time()
    tasks = []
    for i, subtask in enumerate(plan.subtasks):
        tasks.append(run_research_task(client, subtask, i + 1))
        
    # Wait for all tasks in parallel (Join)
    subtask_reports = await asyncio.gather(*tasks)
    exec_elapsed = time.time() - exec_start
    time_tracker["Phase 2: Parallel Research"] = exec_elapsed
    
    console.print()
    console.print("[bold yellow]-- Synchronization Barrier Reached: All parallel research tasks are complete! --[/bold yellow]")
    console.print("[dim]We have successfully waited for all background agents to yield their outputs before progressing.[/dim]\n")
    
    # =======================================================================
    # PHASE 3: CRITIC REVIEW (HANDOFF 1)
    # =======================================================================
    console.print(Rule("[bold]Phase 3: Serial Handoff & Quality Audit[/bold]", style="white"))
    console.print("[dim]Concept: Parallel reports are handed off to a critical auditor to check for contradictions, missing links, and inconsistencies.[/dim]\n")
    
    try:
        critique, c_time = await run_critic(client, topic, subtask_reports)
        time_tracker["Phase 3: Critic Review"] = c_time
    except Exception as e:
        console.print(f"[bold red]Error in Critic Agent:[/bold red] {e}")
        sys.exit(1)
        
    # Display the Critic's Output using our styled chat box
    console.print("\n[bold red]-- Critic's Gap & Alignment Report --------------------[/bold red]")
    print_chat_block(
        agent_name="Research Critic Agent",
        prompt="Review the parallel reports and find any gaps or conflicts.",
        response=critique,
        color_theme="bright_black"
    )
    
    # =======================================================================
    # PHASE 4: SYNTHESIS (HANDOFF 2)
    # =======================================================================
    console.print(Rule("[bold yellow]Phase 4: Master Synthesis & Final Assembly[/bold yellow]", style="yellow"))
    console.print("[dim]Concept: Lead Synthesizer combines individual sections, incorporates Critic notes, and outputs a single cohesive document.[/dim]\n")
    
    try:
        final_report, s_time = await run_synthesis(client, topic, subtask_reports, critique)
        time_tracker["Phase 4: Final Synthesis"] = s_time
    except Exception as e:
        console.print(f"[bold red]Error in Synthesizer Agent:[/bold red] {e}")
        sys.exit(1)
        
    # Write to File
    report_file_path = "research_report.md"
    try:
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(final_report)
        console.print(f"  [green]✓[/green] [bold green]Success![/bold green] Complete master report successfully written to [bold white]{report_file_path}[/bold white]\n")
    except Exception as e:
        console.print(f"[bold red]Error saving report to file:[/bold red] {e}")
        
    # =======================================================================
    # OVERALL SUMMARY & PEDAGOGICAL BREAKDOWN
    # =======================================================================
    console.print(Rule("[bold yellow]Multi-Agent Performance Summary[/bold yellow]", style="yellow"))
    console.print()
    
    total_elapsed = time.time() - total_start
    
    # Print Performance Metrics Table
    summary_table = Table(title="Pipeline Execution Metrics", show_lines=True)
    summary_table.add_column("Pipeline Phase", style="bold")
    summary_table.add_column("Pattern Highlighted", style="dim")
    summary_table.add_column("Duration (Seconds)", justify="right", style="green")
    
    total_individual_time = 0.0
    for phase, p_duration in time_tracker.items():
        if phase == "Phase 2: Parallel Research":
            pattern = "Fork-Join Parallelism"
            # Calculate sum of individual times to show speedup
            indiv_sum = sum(r["elapsed"] for r in subtask_reports)
            speedup = indiv_sum - p_duration
            total_individual_time += indiv_sum
            duration_str = f"{p_duration:.1f}s [dim](Saved {speedup:.1f}s via Parallelism!)[/dim]"
        else:
            if phase == "Phase 1: Planning":
                pattern = "Orchestrator Blueprint"
            elif phase == "Phase 3: Critic Review":
                pattern = "Serial Gatekeeping Handoff"
            else:
                pattern = "Aggregation & Editorial Polish"
            total_individual_time += p_duration
            duration_str = f"{p_duration:.1f}s"
            
        summary_table.add_row(phase, pattern, duration_str)
        
    summary_table.add_section()
    summary_table.add_row(
        "[bold yellow]Total Clock Time[/bold yellow]",
        "[dim]Actual time user waited[/dim]",
        f"[bold yellow]{total_elapsed:.1f}s[/bold yellow]"
    )
    summary_table.add_row(
        "[bold cyan]Cumulative Work Time[/bold cyan]",
        "[dim]Sum of sequential executions[/dim]",
        f"[bold cyan]{total_individual_time:.1f}s[/bold cyan]"
    )
    console.print(summary_table)
    console.print()
    
    # Display teaser of final report
    teaser_lines = []
    lines = final_report.split("\n")
    # Grab the first 25 lines of the report to display
    for line in lines[:25]:
        teaser_lines.append(line)
        
    teaser_text = "\n".join(teaser_lines) + "\n\n... [dim](Report truncated. Read the full document in research_report.md)[/dim]"
    
    console.print(
        Panel(
            teaser_text,
            title=f"[bold green]Master Report Preview (Saved to {report_file_path})[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
    )
    console.print()
    console.print("[bold green]Deep research successfully completed![/bold green] You can open '[bold white]research_report.md[/bold white]' to view the fully detailed, synthesized results.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Pipeline aborted by user.[/bold red]")
        sys.exit(0)
