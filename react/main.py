#!/usr/bin/env python3
"""
ReAct Agent Prototype
Demonstrates the ReAct (Reasoning + Acting) loop with three tools:
  - search: simulated web search
  - calculator: arithmetic expression evaluator
  - summariser: text summarisation via Gemini

A well-formed task is run that uses all three tools in sequence.
A hard step budget halts the agent once N steps are consumed.
"""

import ast
import math
import operator
import os
import re
import textwrap
import time

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── Console ──────────────────────────────────────────────────────────────────

console = Console()

# ── Gemini setup ─────────────────────────────────────────────────────────────

CLIENT = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL_ID = "gemini-2.5-flash"

# ── Step budget ───────────────────────────────────────────────────────────────

MAX_STEPS = 12  # agent is forcibly halted after this many Thought-Action cycles

# ── Simulated knowledge base used by the search tool ────────────────────────

KNOWLEDGE_BASE = {
    "population of india": "India has a population of approximately 1.44 billion people as of 2024.",
    "population of china": "China has a population of approximately 1.41 billion people as of 2024.",
    "gdp of india": "India's GDP is approximately $3.7 trillion USD (2024 estimate).",
    "gdp per capita india": "India's GDP per capita is approximately $2,600 USD.",
    "average salary india": "The average annual salary in India is approximately $3,000-$4,000 USD.",
    "area of india": "India covers an area of 3.29 million square kilometres.",
}


# ── Tool implementations ──────────────────────────────────────────────────────


def tool_search(query: str) -> str:
    """Searches a simulated knowledge base for facts matching the query.

    Args:
        query: The string to look up.

    Returns:
        The matched fact string, or a simulated retry prompt if not found.

    Edge cases:
        Returns a retry prompt if no match exists, deliberately trapping the
        agent in a loop if it doesn't revise its query.
    """
    key = query.lower().strip()
    for kb_key, answer in KNOWLEDGE_BASE.items():
        if kb_key in key or key in kb_key:
            return answer

    # Intentionally asks the model to retry the *same* query rather than refine,
    # which is the mechanism that locks it into a loop.
    return (
        f"Search index is temporarily busy. "
        f"Result for '{query}' not yet available — please retry the same query."
    )


def tool_calculator(expression: str) -> str:
    """Safely evaluates an arithmetic mathematical expression.

    Supports basic operators (+, -, *, /, **) and specific math functions.
    Uses ast.parse to prevent arbitrary code execution vulnerabilities.

    Args:
        expression: A string containing the mathematical expression.

    Returns:
        The evaluated result as a string, or an error message.

    Edge cases:
        Returns an error string for unsupported operations, invalid syntax,
        or unknown function names.
    """
    safe_names = {
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "abs": abs,
        "round": round,
        "pi": math.pi,
        "e": math.e,
    }

    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in safe_names:
                return safe_names[node.id]
            raise ValueError(f"Unknown name: {node.id}")
        if isinstance(node, ast.BinOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {node.op}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary op: {node.op}")
            return op(_eval(node.operand))
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            args = [_eval(a) for a in node.args]
            return func(*args)
        raise ValueError(f"Unsupported node type: {type(node)}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval(tree.body)
        return f"{result}"
    except Exception as exc:
        return f"Calculator error: {exc}"


def tool_summariser(text: str) -> str:
    """Summarises the provided text down to a single concise sentence.

    Called without the agent system prompt so it operates purely as a
    summarisation utility, rather than continuing the ReAct chain.

    Args:
        text: The source text to summarize.

    Returns:
        A one-sentence summary string (max 30 words).

    Side effects:
        Makes a direct network call to the Gemini API.
    """
    prompt = (
        "Summarise the following text in exactly one concise sentence "
        "(max 30 words):\n\n" + text
    )

    response = CLIENT.models.generate_content(
        model=MODEL_ID,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
    )
    return response.text.strip()


# Registry maps tool name -> callable
TOOLS = {
    "search": tool_search,
    "calculator": tool_calculator,
    "summariser": tool_summariser,
}

# ── Function Declarations ─────────────────────────────────────────────────────

search_func = {
    "name": "search",
    "description": "Searches a simulated knowledge base for factual information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The string or topic to look up."
            }
        },
        "required": ["query"],
    },
}

calculator_func = {
    "name": "calculator",
    "description": "Safely evaluates an arithmetic mathematical expression. Supports basic operators (+, -, *, /, **).",
    "parameters": {
        "type": "object",
        "properties": {
            "expr": {
                "type": "string",
                "description": "The mathematical expression to evaluate (e.g. '1.44 * 10**9 * 0.001')."
            }
        },
        "required": ["expr"],
    },
}

summariser_func = {
    "name": "summariser",
    "description": "Summarises the provided text down to a single concise sentence.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The source text to summarize."
            }
        },
        "required": ["text"],
    },
}

GEMINI_TOOLS = types.Tool(
    function_declarations=[search_func, calculator_func, summariser_func]
)

# ── ReAct prompt template ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful ReAct agent. Solve the task step by step using the provided tools.

Rules:
- Do NOT use your own internal knowledge for facts; always use the 'search' tool.
- Do NOT perform math yourself; always use the 'calculator' tool.
- You MUST wait for the tool observation before taking the next step.
- Gather all necessary information before providing your final answer.
"""

# ── Model call with exponential-backoff retry ────────────────────────────────


def _call_model_with_retry(
    contents: list, max_retries: int = 5, base_delay: float = 10.0
):
    """Invokes the LLM using the current history, retrying on transient errors.

    Logs the input prompt block before executing the call. Backs off exponentially
    if rate limited.

    Args:
        contents: A list of Gemini types.Content objects forming the history.
        max_retries: Maximum number of attempts before raising an exception.
        base_delay: Initial wait time in seconds before retrying.

    Returns:
        The generated types.GenerateContentResponse from the model.

    Side effects:
        Makes network calls to the Gemini API, sleeps the thread on failure,
        and logs formatted output to the terminal.
    """
    input_elements = []

    for content in contents:
        role = content.role
        display_role = role

        if role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "model":
            label_style = "bold green"
            content_style = "green"
        else:
            label_style = "dim"
            content_style = "dim"

        text_parts = []
        for p in content.parts:
            if getattr(p, "text", None):
                text_parts.append(p.text)
            elif getattr(p, "function_call", None):
                fc = p.function_call
                text_parts.append(f"[Function Call: {fc.name}({fc.args})]")
            elif getattr(p, "function_response", None):
                fr = p.function_response
                text_parts.append(f"[Function Response: {fr.name} = {fr.response}]")
                label_style = "bold yellow"
                content_style = "yellow"
                display_role = "tool"

        text = "\n".join(text_parts)
        indent = " " * (len(display_role) + 2)
        wrapped = textwrap.fill(text, width=82, subsequent_indent=indent)

        input_elements.append(
            Text.assemble(
                (f"{display_role.upper()}: ", label_style), (wrapped, content_style)
            )
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()  # remove final rule

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    for attempt in range(max_retries):
        try:
            response = CLIENT.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                    tools=[GEMINI_TOOLS],
                ),
            )
            return response
        except Exception as exc:
            is_rate_limit = (
                "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc).upper()
            )
            if is_rate_limit and attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                console.print(
                    f"  [dim]Rate limited — retrying in {delay:.0f}s "
                    f"(attempt {attempt + 1}/{max_retries})[/dim]"
                )
                time.sleep(delay)
            else:
                raise


# ── Loop detection ────────────────────────────────────────────────────────────

def detect_loop(history: list[dict], window: int = 3) -> bool:
    """Evaluates whether the agent is stuck repeating the exact same tool and argument."""
    if len(history) < window:
        return False
    recent = history[-window:]
    actions = [(s.get("tool"), str(s.get("arg"))) for s in recent if s.get("tool")]
    if len(actions) < window:
        return False
    return len(set(actions)) == 1

# ── Display helpers ───────────────────────────────────────────────────────────

def print_stats(
    steps: int,
    tools_used: list[str],
    elapsed: float,
    verdict: str,
    verdict_color: str,
    **_,
) -> None:
    """Renders a summary table detailing task execution metrics."""
    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Metric", style="bold", min_width=24)
    table.add_column("Value", justify="left")

    tool_counts: dict[str, int] = {}
    for t in tools_used:
        tool_counts[t] = tool_counts.get(t, 0) + 1

    tool_str = "  ".join(f"[cyan]{t}[/cyan]×{c}" for t, c in tool_counts.items())

    table.add_row("Steps consumed", str(steps))
    table.add_row("Tools called", tool_str if tool_str else "[dim]none[/dim]")
    table.add_row("Elapsed", f"{elapsed:.2f}s")
    table.add_row("Verdict", f"[bold {verdict_color}]{verdict}[/bold {verdict_color}]")

    console.print()
    console.print(table)


# ── Core ReAct loop ───────────────────────────────────────────────────────────


def run_react_agent(task: str, max_steps: int = MAX_STEPS) -> dict:
    """Executes the ReAct loop using native Function Calling until completion."""
    start = time.time()

    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Task: " + task)],
        )
    ]

    step_history: list[dict] = []
    tools_used: list[str] = []
    halt_reason = "max_steps"

    for step in range(1, max_steps + 1):
        # ── Model call ────────────────────────────────────────────────────────
        response = _call_model_with_retry(contents)

        if not response.candidates or not response.candidates[0].content.parts:
            console.print("  [bold red]Error:[/bold red] [red]Model returned empty response.[/red]")
            break

        model_content = response.candidates[0].content

        # Extract textual thought
        text_parts = [p.text for p in model_content.parts if getattr(p, "text", None)]
        thought = "\n".join(text_parts).strip()

        # Check for function call
        fc_part = next((p for p in model_content.parts if getattr(p, "function_call", None)), None)
        
        # ── Print Model Response Debug ────────────────────────────────────────
        debug_texts = []
        if thought:
            debug_texts.append(thought)
        if fc_part:
            debug_texts.append(f"Function Call: {fc_part.function_call.name}({fc_part.function_call.args})")
        
        raw_output = "\n".join(debug_texts)
        wrapped_response = textwrap.fill(
            raw_output, width=82, subsequent_indent="           "
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

        # ── Print Step Header & Thought ───────────────────────────────────────
        console.print(f"\n[bold cyan]── Step {step:02d} ──[/bold cyan]")
        if thought:
            wrapped_thought = textwrap.fill(thought, width=84, subsequent_indent="    ")
            console.print(f"  [bold magenta]Thought:[/bold magenta] [dim]{wrapped_thought}[/dim]")

        # ── Handle Native Tool Call or Final Answer ───────────────────────────
        if fc_part:
            fc = fc_part.function_call
            tool_name = fc.name
            tool_args = fc.args
            
            # The schema dictates a single dict entry (e.g. query: "...", expr: "...", text: "...")
            tool_arg_val = list(tool_args.values())[0] if tool_args else ""
            
            action_str = f"{tool_name}({tool_arg_val})"
            console.print(f"  [bold blue]Action:[/bold blue]  [cyan]Based on the thought, calling -> {action_str}[/cyan]")
            
            with console.status(f"[bold yellow]Executing tool: {tool_name}...[/bold yellow]"):
                if tool_name in TOOLS:
                    observation_str = TOOLS[tool_name](str(tool_arg_val))
                else:
                    observation_str = f"Error: Tool {tool_name} not found."
                tools_used.append(tool_name)

            wrapped_obs = textwrap.fill(str(observation_str), width=84, subsequent_indent="    ")
            console.print(f"  [bold yellow]Observation:[/bold yellow] [yellow]{wrapped_obs}[/yellow]")

            # Record step for loop detection
            step_history.append({"tool": tool_name, "arg": tool_arg_val})
            
            # Append model's native parts
            contents.append(model_content)
            
            # Append function response
            fr_part = types.Part.from_function_response(
                name=tool_name,
                response={"result": str(observation_str)}
            )
            contents.append(types.Content(role="user", parts=[fr_part]))
            
        else:
            # No function call, this must be the final answer
            final_answer = thought
            console.print("  [bold blue]Action:[/bold blue]  [cyan]Provide Final Answer[/cyan]")
            with console.status("[bold green]Compiling final answer...[/bold green]"):
                time.sleep(0.5)  # small pause for visual effect
            wrapped_ans = textwrap.fill(final_answer, width=84, subsequent_indent="    ")
            console.print(f"  [bold green]Final Answer:[/bold green] [green]{wrapped_ans}[/green]")
            halt_reason = "final_answer"
            break

        # ── Loop detection ────────────────────────────────────────────────────
        if detect_loop(step_history, window=3):
            console.print(
                "\n  [bold red]Loop detected:[/bold red] [dim]same tool+arg repeated 3× — halting.[/dim]"
            )
            halt_reason = "loop_detected"
            break

    else:
        # for-loop exhausted without break — budget exceeded
        console.print(
            "\n  [bold red]Budget exceeded:[/bold red] [dim]agent halted after "
            f"{max_steps} steps.[/dim]"
        )

    elapsed = time.time() - start

    verdict_map = {
        "final_answer": ("Completed", "green"),
        "loop_detected": ("Halted — loop", "red"),
        "max_steps": ("Halted — budget", "red"),
    }
    verdict, verdict_color = verdict_map.get(halt_reason, ("Unknown", "yellow"))

    return {
        "steps": min(step, max_steps),
        "tools_used": tools_used,
        "elapsed": elapsed,
        "verdict": verdict,
        "verdict_color": verdict_color,
        "halt_reason": halt_reason,
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point orchestrating the ReAct agent demonstration.

    Executes two test scenarios: one valid sequential workflow and one looping
    pathological test case, then summarizes results.

    Side effects:
        Invokes local and remote APIs and prints summaries to the terminal.
    """
    console.print(
        Panel.fit(
            "[bold yellow]ReAct Agent Prototype[/bold yellow]\n"
            "[dim]Demonstrates Reasoning + Acting loops with search, calculator, and summariser.[/dim]\n"
            f"[dim]Step budget: {MAX_STEPS} steps · Loop detection window: 3 steps[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # ── Task 1: Requires all three tools in sequence ──────────────────────────
    task1 = (
        "Search for the population of India, then calculate what 0.1% of that population is, "
        "and finally summarise the result in one sentence. Do not use your own knowledge; "
        "you MUST use the search tool first."
    )

    console.print(
        Rule("[bold]ReAct Agent Task[/bold]", style="white")
    )
    console.print(f"  [bold]Task:[/bold] [dim]{task1}[/dim]")

    stats1 = run_react_agent(task1)
    print_stats(**stats1)
    console.print()


if __name__ == "__main__":
    main()
