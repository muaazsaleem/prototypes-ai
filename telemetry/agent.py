#!/usr/bin/env python3
"""OpenTelemetry Trace for an Agent Run.

Demonstrates how Langfuse tracing turns multi-step agent debugging
from guesswork into directed investigation.
"""

import os
import textwrap
import time
from dataclasses import dataclass

from google import genai
from google.genai import types
from langfuse import Langfuse
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"

# Gemini 2.5 Flash pricing (USD per 1 million tokens)
COST_PER_1M_INPUT = 0.075
COST_PER_1M_OUTPUT = 0.30

# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

langfuse = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

console = Console()

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SpanRecord:
    """Holds local timing and metadata for one span so we can build the summary table."""

    name: str
    span_type: str  # "llm" | "tool"
    step: int
    duration_s: float
    success: bool
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_name: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def calculator(expression: str) -> str:
    """Evaluates a math expression restricted to numeric operators; rejects arbitrary code."""
    allowed = set("0123456789+-*/()., ")
    if not all(c in allowed for c in expression):
        raise ValueError(f"Unsafe expression rejected: {expression!r}")
    return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307


def get_weather(city: str) -> str:
    """Returns mock weather data; sleeps 2.5 s to simulate a slow external API call."""
    # Intentional delay — makes this the slow span the trace must identify
    time.sleep(2.5)
    if city.lower() in ("error_city", "invalid", "nowhere"):
        raise ValueError(f"City not found in weather service: {city!r}")
    mock: dict[str, str] = {
        "paris": "Partly cloudy, 18 C, humidity 65%",
        "london": "Overcast and rainy, 12 C, humidity 88%",
        "tokyo": "Sunny, 24 C, humidity 52%",
        "new york": "Windy and clear, 15 C, humidity 43%",
    }
    return mock.get(city.lower(), f"Clear skies, 20 C in {city}")


def search_news(query: str) -> str:
    """Returns three mock news headlines for a query with a 0.3 s simulated latency."""
    time.sleep(0.3)
    return (
        f"Top results for '{query}': "
        "(1) Major breakthrough announced. "
        "(2) Experts weigh in on latest development. "
        "(3) Industry report highlights key trends for 2025."
    )


TOOL_REGISTRY = {
    "calculator": calculator,
    "get_weather": get_weather,
    "search_news": search_news,
}

# Gemini function declarations that mirror the tool signatures above
TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="calculator",
                description="Evaluates a mathematical expression using standard Python operators.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "expression": types.Schema(
                            type=types.Type.STRING,
                            description="Math expression, e.g. '0.15 * 2847'",
                        )
                    },
                    required=["expression"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_weather",
                description="Returns the current weather conditions for a given city.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="City name, e.g. 'Paris'",
                        )
                    },
                    required=["city"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_news",
                description="Searches recent news on a topic and returns the top 3 results.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Search topic or keyword",
                        )
                    },
                    required=["query"],
                ),
            ),
        ]
    )
]

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use tools as needed to answer the user's question, "
    "then provide a concise final answer. Do not call the same tool twice with identical arguments."
)

# ---------------------------------------------------------------------------
# Cost helper
# ---------------------------------------------------------------------------


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    """Returns the USD cost of one Gemini 2.5 Flash call given its token counts."""
    return (
        input_tokens / 1_000_000 * COST_PER_1M_INPUT
        + output_tokens / 1_000_000 * COST_PER_1M_OUTPUT
    )


# ---------------------------------------------------------------------------
# Content serialisation helper (for Langfuse input logging)
# ---------------------------------------------------------------------------


def serialize_contents(contents: list) -> list[dict]:
    """Converts google-genai Content objects into JSON-serialisable dicts for Langfuse.

    Each content item maps to {role, parts: [{type, ...}]}.
    """
    result = []
    for msg in contents:
        role = getattr(msg, "role", "user")
        parts_out = []
        for p in msg.parts:
            if getattr(p, "text", None):
                parts_out.append({"type": "text", "text": p.text})
            elif getattr(p, "function_call", None) and p.function_call.name:
                fc = p.function_call
                parts_out.append(
                    {"type": "function_call", "name": fc.name, "args": dict(fc.args)}
                )
            elif getattr(p, "function_response", None):
                fr = p.function_response
                parts_out.append(
                    {
                        "type": "function_response",
                        "name": fr.name,
                        "response": dict(fr.response),
                    }
                )
        result.append({"role": role, "parts": parts_out})
    return result


# ---------------------------------------------------------------------------
# Terminal display helpers  (follow terminal-output-style conventions)
# ---------------------------------------------------------------------------


def display_llm_input(contents: list, step: int) -> None:
    """Renders the full conversation history being sent to Gemini in a grey panel."""
    console.print()
    console.print(Rule(f"[bold]Step {step} — LLM Call[/bold]", style="white"))
    console.print()

    input_elements = []
    for msg in contents:
        role = getattr(msg, "role", "user")

        # Flatten all parts into one readable string for display
        parts_text = []
        for p in msg.parts:
            if getattr(p, "text", None):
                parts_text.append(p.text)
            elif getattr(p, "function_call", None) and p.function_call.name:
                fc = p.function_call
                parts_text.append(f"[function_call: {fc.name}({dict(fc.args)})]")
            elif getattr(p, "function_response", None):
                fr = p.function_response
                parts_text.append(
                    f"[function_response: {fr.name} → {dict(fr.response)}]"
                )
        content_str = " ".join(parts_text) or "(empty)"

        label_style = "bold blue" if role == "user" else "bold green"
        content_style = "blue" if role == "user" else "green"
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content_str, width=82, subsequent_indent=indent)

        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()  # remove trailing rule

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_llm_response(text: str) -> None:
    """Renders the model's response (or a tool-call placeholder) in a grey panel."""
    wrapped = textwrap.fill(text, width=82, subsequent_indent="           ")
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


def display_trace_table(spans: list[SpanRecord], run_label: str, success: bool) -> None:
    """Renders a per-span summary table for one agent run, flagging the slowest span."""
    status = (
        "[bold green]SUCCESS[/bold green]" if success else "[bold red]FAILED[/bold red]"
    )
    console.print(
        Rule(f"[bold]Trace Summary — {run_label}  {status}[/bold]", style="white")
    )
    console.print()

    # The slowest span across any type gets a visual marker
    slowest = max(spans, key=lambda s: s.duration_s) if spans else None

    table = Table(
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        show_edge=False,
        show_lines=True,
    )
    table.add_column("Span Name", style="bold", min_width=28)
    table.add_column("Type", justify="center", min_width=7)
    table.add_column("Step", justify="center", min_width=5)
    table.add_column("Duration", justify="right", min_width=16)
    table.add_column("Tokens in/out", justify="center", min_width=14)
    table.add_column("Cost (USD)", justify="right", min_width=13)
    table.add_column("Status", justify="center", min_width=10)

    total_cost = 0.0
    total_dur = 0.0

    for span in spans:
        total_cost += span.cost_usd
        total_dur += span.duration_s

        dur_text = f"{span.duration_s:.2f}s"
        dur_cell = (
            f"[bold yellow]{dur_text} ◄ SLOW[/bold yellow]"
            if span is slowest
            else dur_text
        )
        type_cell = (
            "[cyan]LLM[/cyan]" if span.span_type == "llm" else "[magenta]TOOL[/magenta]"
        )
        tokens_cell = (
            f"{span.input_tokens}/{span.output_tokens}"
            if span.span_type == "llm"
            else "—"
        )
        cost_cell = f"${span.cost_usd:.6f}" if span.span_type == "llm" else "—"

        if span.success:
            status_cell = "[green]ok[/green]"
        else:
            short_err = span.error[:30] + ("..." if len(span.error) > 30 else "")
            status_cell = f"[red]FAIL[/red]\n[dim red]{short_err}[/dim red]"

        table.add_row(
            span.name,
            type_cell,
            str(span.step),
            dur_cell,
            tokens_cell,
            cost_cell,
            status_cell,
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        f"[bold]{total_dur:.2f}s[/bold]",
        "",
        f"[bold]${total_cost:.6f}[/bold]",
        "",
    )

    console.print(table)
    console.print()


def display_comparison(
    success_spans: list[SpanRecord],
    failed_spans: list[SpanRecord],
    success_answer: str,
    failed_error: str,
    success_url: str,
    failed_url: str,
) -> None:
    """Renders a side-by-side metric comparison of the successful vs failed run."""
    console.print(
        Rule(
            "[bold yellow]Comparison — Successful vs Failed Run[/bold yellow]",
            style="yellow",
        )
    )
    console.print()

    def total_cost(spans: list[SpanRecord]) -> float:
        return sum(s.cost_usd for s in spans)

    def total_dur(spans: list[SpanRecord]) -> float:
        return sum(s.duration_s for s in spans)

    def count_type(spans: list[SpanRecord], t: str) -> int:
        return sum(1 for s in spans if s.span_type == t)

    def total_tokens(spans: list[SpanRecord]) -> int:
        return sum(s.input_tokens + s.output_tokens for s in spans)

    def slow_name(spans: list[SpanRecord]) -> str:
        if not spans:
            return "—"
        s = max(spans, key=lambda x: x.duration_s)
        return f"{s.name}\n({s.duration_s:.2f}s)"

    table = Table(show_header=True, header_style="bold", show_lines=True)
    table.add_column("Metric", style="bold", min_width=18)
    table.add_column("Successful Run", justify="center", min_width=28)
    table.add_column("Failed Run", justify="center", min_width=28)

    rows = [
        ("Total Spans", str(len(success_spans)), str(len(failed_spans))),
        (
            "LLM Calls",
            str(count_type(success_spans, "llm")),
            str(count_type(failed_spans, "llm")),
        ),
        (
            "Tool Calls",
            str(count_type(success_spans, "tool")),
            str(count_type(failed_spans, "tool")),
        ),
        (
            "Total Duration",
            f"{total_dur(success_spans):.2f}s",
            f"{total_dur(failed_spans):.2f}s",
        ),
        (
            "Total Tokens",
            str(total_tokens(success_spans)),
            str(total_tokens(failed_spans)),
        ),
        (
            "Total Cost",
            f"${total_cost(success_spans):.6f}",
            f"${total_cost(failed_spans):.6f}",
        ),
        ("Slowest Span", slow_name(success_spans), slow_name(failed_spans)),
    ]
    for label, s_val, f_val in rows:
        table.add_row(
            label,
            f"[green]{s_val}[/green]",
            f"[red]{f_val}[/red]",
        )

    table.add_section()
    s_out = (
        (success_answer[:50] + "...") if len(success_answer) > 50 else success_answer
    )
    f_out = (
        f"Error: {failed_error[:46]}..."
        if len(failed_error) > 46
        else f"Error: {failed_error}"
    )
    table.add_row(
        "[bold]Outcome[/bold]",
        f"[green]{s_out}[/green]",
        f"[red]{f_out}[/red]",
    )

    console.print(table)
    console.print()

    # Identify the globally slowest span across both runs
    all_spans = success_spans + failed_spans
    if all_spans:
        slowest = max(all_spans, key=lambda s: s.duration_s)
        console.print(
            f"  [bold yellow]Identified Slow Span:[/bold yellow] "
            f"[yellow]{slowest.name}[/yellow] "
            f"took [bold yellow]{slowest.duration_s:.2f}s[/bold yellow] "
            f"[dim](get_weather simulates a slow external API)[/dim]"
        )

    console.print()
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    console.print(f"  [bold]Langfuse host:[/bold] [dim]{host}[/dim]")
    if success_url:
        console.print(f"  [bold]Successful trace:[/bold] [dim]{success_url}[/dim]")
    if failed_url:
        console.print(f"  [bold]Failed trace:    [/bold] [dim]{failed_url}[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def run_agent(
    task: str,
    run_label: str,
    force_fail: bool = False,
) -> tuple[list[SpanRecord], bool, str, str]:
    """Runs a multi-step ReAct agent with full Langfuse tracing.

    Creates one root trace (agent), one generation span per LLM call, and one
    tool span per tool invocation — all properly nested via OTEL context.

    force_fail injects an invalid city into get_weather to simulate a tool error.

    Returns (span_records, success, output_or_error, langfuse_trace_url).
    """
    span_records: list[SpanRecord] = []
    final_output = ""
    run_success = True
    trace_id = ""

    # The outermost context manager creates the root trace in Langfuse
    with langfuse.start_as_current_observation(
        name="agent-run",
        as_type="agent",
        input={"task": task},
        metadata={"run_label": run_label, "model": MODEL_NAME},
    ) as root:
        # Capture trace id before any inner spans overwrite the current context
        trace_id = langfuse.get_current_trace_id() or ""

        try:
            # Conversation history: grows as tool results are fed back to the model
            contents = [types.Content(role="user", parts=[types.Part.from_text(task)])]
            step = 0

            while step < 10:  # guard against infinite loops
                step += 1
                llm_start = time.time()

                # Each LLM call gets its own generation span nested under the root
                with langfuse.start_as_current_observation(
                    name=f"llm-call/step-{step}",
                    as_type="generation",
                    model=MODEL_NAME,
                    input=serialize_contents(contents),
                    metadata={"step_index": step},
                ) as gen:
                    display_llm_input(contents, step)

                    response = gemini_client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=TOOLS,
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.0,
                        ),
                    )

                    llm_duration = time.time() - llm_start

                    usage = response.usage_metadata
                    in_tok = getattr(usage, "prompt_token_count", 0) or 0
                    out_tok = getattr(usage, "candidates_token_count", 0) or 0
                    cost = compute_cost(in_tok, out_tok)

                    # Extract text if the model returned prose instead of a tool call
                    resp_text = ""
                    for part in response.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            resp_text = part.text

                    display_llm_response(resp_text or "[tool call — no text yet]")

                    # Attach usage and cost to the generation span
                    gen.update(
                        output=resp_text or "[function call]",
                        usage_details={"input": in_tok, "output": out_tok},
                        cost_details={
                            "input": in_tok / 1_000_000 * COST_PER_1M_INPUT,
                            "output": out_tok / 1_000_000 * COST_PER_1M_OUTPUT,
                        },
                        metadata={
                            "step_index": step,
                            "duration_s": round(llm_duration, 3),
                            "model": MODEL_NAME,
                        },
                    )

                span_records.append(
                    SpanRecord(
                        name=f"llm-call/step-{step}",
                        span_type="llm",
                        step=step,
                        duration_s=llm_duration,
                        success=True,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost,
                    )
                )

                # Check whether the model issued any function calls
                has_fc = any(
                    getattr(p, "function_call", None) and p.function_call.name
                    for p in response.candidates[0].content.parts
                )

                if not has_fc:
                    # Model returned a final answer — we are done
                    final_output = resp_text
                    contents.append(response.candidates[0].content)
                    break

                # Append the model's function-call turn to conversation history
                contents.append(response.candidates[0].content)

                # Execute each requested tool and collect responses
                tool_response_parts: list[types.Part] = []

                for part in response.candidates[0].content.parts:
                    fc = getattr(part, "function_call", None)
                    if not (fc and fc.name):
                        continue

                    tool_name = fc.name
                    tool_args = dict(fc.args)

                    # Inject the failure scenario for the demo
                    if force_fail and tool_name == "get_weather":
                        tool_args["city"] = "error_city"

                    console.print(
                        f"\n  [bold cyan]> Tool:[/bold cyan] "
                        f"[cyan]{tool_name}[/cyan]  [dim]{tool_args}[/dim]"
                    )

                    tool_ok = True
                    tool_error = ""
                    tool_result = ""
                    tool_duration = 0.0

                    # Each tool call gets its own span nested under the current LLM step
                    with langfuse.start_as_current_observation(
                        name=f"tool/{tool_name}",
                        as_type="tool",
                        input={"tool_name": tool_name, "args": tool_args},
                        metadata={"step_index": step, "tool_name": tool_name},
                    ) as tool_span:
                        tool_start = time.time()
                        try:
                            fn = TOOL_REGISTRY[tool_name]
                            tool_result = fn(**tool_args)
                            tool_span.update(output={"result": tool_result})
                            console.print(
                                f"  [bold yellow]  ↳ Result:[/bold yellow] "
                                f"[yellow]{tool_result}[/yellow]"
                            )
                        except Exception as exc:
                            tool_error = str(exc)
                            tool_ok = False
                            tool_span.update(
                                output={"error": tool_error},
                                level="ERROR",
                                status_message=tool_error,
                            )
                            console.print(
                                f"  [bold red]  ↳ Error:[/bold red] [red]{tool_error}[/red]"
                            )
                        finally:
                            # Record wall-clock duration regardless of success or failure
                            tool_duration = time.time() - tool_start

                    span_records.append(
                        SpanRecord(
                            name=f"tool/{tool_name}/step-{step}",
                            span_type="tool",
                            step=step,
                            duration_s=tool_duration,
                            success=tool_ok,
                            tool_name=tool_name,
                            error=tool_error,
                        )
                    )

                    if not tool_ok:
                        raise RuntimeError(f"Tool '{tool_name}' failed: {tool_error}")

                    # Build the Gemini function-response part to feed back to the model
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )

                # Feed all tool results back as a single user turn
                if tool_response_parts:
                    contents.append(
                        types.Content(role="user", parts=tool_response_parts)
                    )

            root.update(output={"answer": final_output})

        except Exception as exc:
            run_success = False
            final_output = str(exc)
            root.update(
                output={"error": final_output},
                level="ERROR",
                status_message=f"Agent failed: {final_output}",
            )

    # Flush ensures spans reach Langfuse before we print the summary
    langfuse.flush()
    trace_url = langfuse.get_trace_url(trace_id=trace_id) or ""
    return span_records, run_success, final_output, trace_url


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Runs one successful and one failed agent trace, then prints a side-by-side comparison."""
    console.print(
        Panel.fit(
            "[bold yellow]OpenTelemetry Trace for an Agent Run[/bold yellow]\n"
            "[dim]Instruments a multi-step ReAct agent with Langfuse tracing.[/dim]\n"
            "[dim]Successful run + failed run → comparison table → slow span identified.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # ── Run 1: success ────────────────────────────────────────────────────────

    console.print(Rule("[bold]Run 1 — Successful Agent Run[/bold]", style="white"))
    console.print()

    success_task = (
        "What is the current weather in Paris? "
        "Also compute 15% of 2847. "
        "And search for the latest news on artificial intelligence."
    )
    console.print(f"  [bold]Task:[/bold] [dim]{success_task}[/dim]")
    console.print()

    success_spans, success_ok, success_output, success_url = run_agent(
        task=success_task,
        run_label="success",
        force_fail=False,
    )
    display_trace_table(success_spans, "Successful Run", success_ok)

    # ── Run 2: failure ────────────────────────────────────────────────────────

    console.print(Rule("[bold]Run 2 — Failed Agent Run[/bold]", style="white"))
    console.print()

    fail_task = "What is the weather in Paris? " "Also compute 15% of 2847."
    console.print(f"  [bold]Task:[/bold] [dim]{fail_task}[/dim]")
    console.print(
        "  [dim](get_weather will receive an invalid city to simulate a tool failure)[/dim]"
    )
    console.print()

    failed_spans, failed_ok, failed_output, failed_url = run_agent(
        task=fail_task,
        run_label="failure",
        force_fail=True,
    )
    display_trace_table(failed_spans, "Failed Run", failed_ok)

    # ── Comparison ────────────────────────────────────────────────────────────

    display_comparison(
        success_spans,
        failed_spans,
        success_output,
        failed_output,
        success_url,
        failed_url,
    )


if __name__ == "__main__":
    main()
