#!/usr/bin/env python3
"""
ReAct Agent Prototype
Demonstrates the ReAct (Reasoning + Acting) loop with three tools:
  - search: simulated web search
  - calculator: arithmetic expression evaluator
  - summariser: text summarisation via Gemini

Two tasks are run:
  1. A well-formed task that uses all three tools in sequence.
  2. A pathological task designed to trigger a tool-call loop.

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
MODEL_ID = "gemini-2.0-flash"

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

# ── ReAct prompt template ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a ReAct agent. Solve the task step by step using the tools below.

Available tools:
- search(query)      : search for factual information
- calculator(expr)   : evaluate a mathematical expression
- summariser(text)   : summarise a piece of text into one sentence

Output format — you MUST follow this strictly:
Thought: <your reasoning about what to do next>
Action: <tool_name>(<argument>)

When you have the final answer output ONLY:
Final Answer: <your answer>

Rules:
- One Action per turn.
- Do NOT include Observation in your output; the system provides it.
- Do NOT output anything outside the Thought/Action/Final Answer format.
"""


# ── Model call with exponential-backoff retry ────────────────────────────────


def _call_model_with_retry(
    contents: list, max_retries: int = 5, base_delay: float = 10.0
) -> str:
    """Invokes the LLM using the current history, retrying on transient errors.

    Logs the input prompt block before executing the call. Backs off exponentially
    if rate limited.

    Args:
        contents: A list of Gemini types.Content objects forming the history.
        max_retries: Maximum number of attempts before raising an exception.
        base_delay: Initial wait time in seconds before retrying.

    Returns:
        The generated text response from the model.

    Side effects:
        Makes network calls to the Gemini API, sleeps the thread on failure,
        and logs formatted output to the terminal.
    """
    input_elements = []

    for content in contents:
        role = content.role
        text = "\n".join([p.text for p in content.parts if p.text])

        # Override styling if the user message is an Observation
        if role == "user":
            if text.startswith("Observation:"):
                label_style = "bold yellow"
                content_style = "yellow"
                display_role = "tool"
            else:
                label_style = "bold blue"
                content_style = "blue"
                display_role = "user"
        elif role == "model":
            label_style = "bold green"
            content_style = "green"
            display_role = "assistant"
        else:
            label_style = "dim"
            content_style = "dim"
            display_role = role

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
                ),
            )
            return response.text.strip()
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


# ── Parsing helpers ───────────────────────────────────────────────────────────


def parse_agent_output(text: str) -> dict:
    """Extracts the ReAct components (Thought, Action, Final Answer) from model text.

    Args:
        text: The raw output string from the ReAct agent.

    Returns:
        A dictionary containing keys: thought, action, tool, arg, and final_answer.
    """
    result = {
        "thought": "",
        "action": "",
        "tool": None,
        "arg": None,
        "final_answer": None,
    }

    # Extract Thought
    thought_match = re.search(
        r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", text, re.DOTALL
    )
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # Extract Final Answer
    final_match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    if final_match:
        result["final_answer"] = final_match.group(1).strip()
        return result

    # Extract Action: tool_name(argument)
    action_match = re.search(
        r"Action:\s*(\w+)\((.+?)\)\s*$", text, re.DOTALL | re.MULTILINE
    )
    if action_match:
        result["action"] = action_match.group(0).replace("Action:", "").strip()
        result["tool"] = action_match.group(1).strip()
        result["arg"] = action_match.group(2).strip().strip("\"'")

    return result


# ── Loop detection ────────────────────────────────────────────────────────────


def detect_loop(history: list[dict], window: int = 3) -> bool:
    """Evaluates whether the agent is stuck repeating the exact same tool and argument.

    Args:
        history: A list of dictionary objects describing each step's action.
        window: The number of consecutive identical actions required to trigger detection.

    Returns:
        True if a loop is detected, False otherwise.
    """
    if len(history) < window:
        return False
    recent = history[-window:]
    actions = [(s.get("tool"), s.get("arg")) for s in recent if s.get("tool")]
    if len(actions) < window:
        return False
    return len(set(actions)) == 1


# ── Display helpers ───────────────────────────────────────────────────────────


def print_step(step: int, thought: str, action: str, observation: str) -> None:
    """Prints the Thought, Action, and Observation for a single ReAct step.

    Args:
        step: The current 1-based step counter.
        thought: The parsed reasoning trace.
        action: The string representation of the tool invocation.
        observation: The result returned by the invoked tool.

    Side effects:
        Prints formatted output to the terminal.
    """
    console.print(f"\n[bold cyan]> Step {step:02d}[/bold cyan]")

    prefix = "[dim]Thought:[/dim]"
    wrapped = textwrap.fill(thought, width=88, subsequent_indent="           ")
    console.print(f"  {prefix} [dim]{wrapped}[/dim]")

    prefix = "[dim]Action:[/dim]"
    wrapped = textwrap.fill(action, width=88, subsequent_indent="          ")
    console.print(f"  {prefix}  [magenta]{wrapped}[/magenta]")

    prefix = "[dim]Observe:[/dim]"
    obs_wrapped = textwrap.fill(observation, width=88, subsequent_indent="          ")
    console.print(f"  {prefix} [yellow]{obs_wrapped}[/yellow]")


def print_stats(
    steps: int,
    tools_used: list[str],
    elapsed: float,
    verdict: str,
    verdict_color: str,
    **_,
) -> None:
    """Renders a summary table detailing task execution metrics.

    Args:
        steps: Total steps consumed by the agent.
        tools_used: A list of strings naming the invoked tools in order.
        elapsed: The wall-clock execution time in seconds.
        verdict: The final resolution state of the agent (e.g. Completed).
        verdict_color: The rich styling color representing the outcome.

    Side effects:
        Prints a rich Table to the terminal.
    """
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
    """Executes the ReAct loop until completion, failure, or budget exhaustion.

    Args:
        task: The high-level instruction given to the agent.
        max_steps: The absolute maximum number of steps allowed before halting.

    Returns:
        A dictionary containing run statistics such as steps taken, tools used,
        elapsed time, and the final verdict string.

    Side effects:
        Modifies local state lists, interacts with external APIs, and prints logs.
    """
    start = time.time()

    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part(text="Task: " + task)],
        )
    ]

    step_history: list[dict] = []
    tools_used: list[str] = []
    halt_reason = "max_steps"

    for step in range(1, max_steps + 1):
        # ── Model call ────────────────────────────────────────────────────────
        raw_output = _call_model_with_retry(contents)

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

        parsed = parse_agent_output(raw_output)
        thought = parsed["thought"]
        tool_name = parsed["tool"]
        tool_arg = parsed["arg"]
        final_answer = parsed["final_answer"]

        # ── Final answer ──────────────────────────────────────────────────────
        if final_answer:
            print_step(
                step, thought or "Compiling answer.", "Final Answer", final_answer
            )
            halt_reason = "final_answer"
            break

        # ── Execute tool ──────────────────────────────────────────────────────
        if tool_name and tool_name in TOOLS:
            observation = TOOLS[tool_name](tool_arg)
            tools_used.append(tool_name)
        else:
            # Model produced malformed output; nudge it back on track
            observation = "Invalid action. Use format: tool_name(argument)"
            tool_name = "invalid"
            tool_arg = raw_output[:60]

        action_str = f"{tool_name}({tool_arg})"
        print_step(step, thought, action_str, observation)

        # Record step for loop detection
        step_history.append({"tool": tool_name, "arg": tool_arg})

        # ── Loop detection ────────────────────────────────────────────────────
        if detect_loop(step_history, window=3):
            console.print(
                "\n  [bold red]Loop detected:[/bold red] [dim]same tool+arg repeated 3× — halting.[/dim]"
            )
            halt_reason = "loop_detected"
            break

        # ── Append observation so the model can reason in the next turn ───────
        contents.append(
            types.Content(role="model", parts=[types.Part(text=raw_output)])
        )
        contents.append(
            types.Content(
                role="user", parts=[types.Part(text=f"Observation: {observation}")]
            )
        )

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
        "Find the population of India, then calculate what 0.1% of that population is, "
        "and finally summarise the result in one sentence."
    )

    console.print(
        Rule("[bold]Task 1 — All three tools in sequence[/bold]", style="white")
    )
    console.print(f"  [bold]Task:[/bold] [dim]{task1}[/dim]")

    stats1 = run_react_agent(task1)
    print_stats(**stats1)
    console.print()

    # ── Task 2: Designed to trigger a tool-call loop ──────────────────────────
    # The query is pinned to a specific string the model is told to use verbatim.
    # The search tool responds "retry the same query", trapping the agent in a
    # loop of calling search("real-time AAPL stock price") indefinitely.
    task2 = (
        "Fetch the real-time stock price of AAPL using search('real-time AAPL stock price'). "
        "The search index is live and will return the price eventually. "
        "You MUST use that exact query every time. Keep retrying until you get a number."
    )

    console.print(
        Rule("[bold]Task 2 — Pathological looping task[/bold]", style="white")
    )
    console.print(f"  [bold]Task:[/bold] [dim]{task2}[/dim]")

    stats2 = run_react_agent(task2)
    print_stats(**stats2)
    console.print()

    # ── Overall summary ───────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))

    summary = Table(title="Results", show_lines=True)
    summary.add_column("Task", style="bold", min_width=24)
    summary.add_column("Steps", justify="center")
    summary.add_column("Tools Called", justify="center")
    summary.add_column("Elapsed", justify="center")
    summary.add_column("Verdict", justify="center")

    for label, stats in [("Task 1", stats1), ("Task 2", stats2)]:
        tool_counts: dict[str, int] = {}
        for t in stats["tools_used"]:
            tool_counts[t] = tool_counts.get(t, 0) + 1
        tools_str = ", ".join(f"{t}×{c}" for t, c in tool_counts.items()) or "none"
        color = stats["verdict_color"]
        summary.add_row(
            label,
            str(stats["steps"]),
            tools_str,
            f"{stats['elapsed']:.2f}s",
            f"[bold {color}]{stats['verdict']}[/bold {color}]",
        )

    console.print(summary)
    console.print()


if __name__ == "__main__":
    main()
