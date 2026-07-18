"""
ReAct Loop (Reason + Act) for Paper-to-Code Agent.

Each iteration:
  1. OBSERVE  -- current context (paper text, prior thoughts, tool results)
  2. THINK    -- LLM reasons about what to do next
  3. ACT      -- execute the chosen tool
  4. REFLECT  -- check if the task is complete; loop or finish

The loop terminates when the LLM emits the `finish` tool with the final
code, or when the step budget is exhausted.
"""

from __future__ import annotations

import os
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from tools import TOOL_DEFINITIONS, dispatch_tool

console = Console()

# Maximum ReAct iterations before we force a finish
MAX_STEPS = 20
MODEL = "gemini-2.5-flash"


@dataclass
class AgentState:
    """Mutable state threaded through the ReAct loop."""
    paper_text: str
    output_path: str
    messages: list[types.Content] = field(default_factory=list)
    steps: int = 0
    final_code: str | None = None
    done: bool = False


def _system_prompt(paper_text: str, output_path: str) -> str:
    return f"""You are an expert software engineer that implements algorithms and systems from \
research papers.

## Your task
Read the paper below and produce working, well-commented Python code that implements the \
core contribution of the paper.  The code must be saved to: {output_path}

## ReAct loop instructions
You operate in a Reason-Act loop.  At every step you MUST:
1. Write a short THOUGHT explaining what you will do and why.
2. Call exactly ONE tool to act on that thought.
3. Run until code works.

Available tools:
- `extract_section`  -- pull a named section from the paper for closer inspection
- `write_code`       -- write a complete Python code block to a scratch buffer
- `run_code`         -- execute the current scratch buffer; returns stdout/stderr
- `finish`           -- save the final code to disk and terminate the loop

Rules:
- Always think before acting.
- After `run_code`, inspect the output.  If there are errors, fix them with `write_code` \
  then `run_code` again.
- Call `finish` only when the code is correct (run_code showed no fatal errors).
- Do NOT call `finish` before running the code at least once.
- Keep the implementation focused on the paper's core algorithm.  Do not pad with unrelated code.

## Paper text
---
{paper_text[:60_000]}
---
"""


def _print_step_header(step: int) -> None:
    console.print(Rule(f"[bold]STEP {step}[/bold]", style="white"))
    console.print()


def _print_model_input(system_prompt: str, messages: list[types.Content]) -> None:
    input_elements = []
    
    # System Instruction
    indent = " " * 8
    wrapped = textwrap.fill("...", width=82, subsequent_indent=indent)
    input_elements.append(Text.assemble(("SYSTEM: ", "dim"), (wrapped, "dim")))
    input_elements.append(Rule(style="bright_black"))

    for msg in messages[-1:]:
        role = msg.role or "user"
        for part in msg.parts:
            content = ""
            if part.text:
                content = part.text
            elif part.function_call:
                content = f"CALL: {part.function_call.name}({part.function_call.args})"
            elif part.function_response:
                content = f"RESPONSE: {part.function_response.response}"
            
            if not content:
                continue

            if role == "user":
                label_style = "bold blue"
                content_style = "blue"
                display_role = "USER"
            elif role == "model":
                label_style = "bold green"
                content_style = "green"
                display_role = "ASSISTANT"
            else:
                label_style = "bold yellow"
                content_style = "yellow"
                display_role = role.upper()

            indent = " " * (len(display_role) + 2)
            wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
            input_elements.append(Text.assemble((f"{display_role}: ", label_style), (wrapped, content_style)))
            input_elements.append(Rule(style="bright_black"))
    if input_elements:
        input_elements.pop()

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def _print_model_output(response_text: str) -> None:
    wrapped_response = textwrap.fill(response_text, width=82, subsequent_indent="           ")
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic")
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


def _print_tool_call(name: str, args: dict) -> None:
    console.print(f"[bold magenta]> ACT: {name}[/bold magenta]")
    if args:
        console.print(f"  [dim]Args: {args}[/dim]")


def _print_tool_result(result: str) -> None:
    console.print(f"\n[bold yellow]> TOOL RESULT[/bold yellow]")
    wrapped = textwrap.fill(str(result), width=88, subsequent_indent="         ")
    console.print(f"  [yellow]{wrapped}[/yellow]\n")


def _get_gemini_tools() -> list[types.Tool]:
    """Convert Anthropic-style tool definitions to google-genai tools."""
    decls = []
    for t in TOOL_DEFINITIONS:
        schema = t["input_schema"]
        decls.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=schema
            )
        )
    return [types.Tool(function_declarations=decls)]


def run(state: AgentState) -> str:
    """Execute the ReAct loop using the new google-genai SDK."""
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    gemini_tools = _get_gemini_tools()
    system_instruction = _system_prompt(state.paper_text, state.output_path)

    # Print the system prompt once
    console.print(
        Panel(
            system_instruction,
            title="[bold bright_black]System Prompt[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    # Initial user request
    user_content = types.Content(
        role="user",
        parts=[types.Part(text=(
            "Implement the core algorithm from the paper as working Python code. "
            "Begin by reasoning about the paper's central contribution, then act step by step."
        ))]
    )
    state.messages.append(user_content)

    while not state.done and state.steps < MAX_STEPS:
        state.steps += 1
        _print_step_header(state.steps)
        
        # Log the full conversation history before each turn
        _print_model_input(system_instruction, state.messages)

        response = client.models.generate_content(
            model=MODEL,
            contents=state.messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
            )
        )

        assistant_parts = []
        thought = None
        tool_call = None

        for part in response.candidates[0].content.parts:
            if part.text:
                assistant_parts.append(types.Part(text=part.text))
                if not thought:
                    thought = part.text
            if part.function_call:
                assistant_parts.append(part)
                if not tool_call:
                    tool_call = part.function_call

        state.messages.append(types.Content(role="model", parts=assistant_parts))

        if thought:
            _print_model_output(thought)

        if not tool_call:
            nudge = types.Content(
                role="user",
                parts=[types.Part(text="Please call a tool to continue.")]
            )
            state.messages.append(nudge)
            continue

        name = tool_call.name
        args = tool_call.args

        _print_tool_call(name, args)
        
        result, done, code = dispatch_tool(name, args, state.paper_text)
        _print_tool_result(result)

        # Append tool result to history
        state.messages.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=name,
                            response={"result": result}
                        )
                    )
                ]
            )
        )

        if done:
            state.final_code = code
            state.done = True
            break

    if not state.final_code:
        raise RuntimeError(
            f"Agent exhausted {MAX_STEPS} steps without producing final code."
        )

    return state.final_code
