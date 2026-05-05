#!/usr/bin/env python3
"""
Prototype: Plan-and-Execute Agent

This prototype demonstrates a Plan-and-Execute agentic architecture handling a
procurement task. The catalog features cascading failures (out-of-stock items
whose alternatives are ALSO out of stock).

Plan-and-Execute generates a rigid plan that shatters upon contact with reality.

Updated to use the modern google-genai SDK.
"""

import json
import os
import textwrap
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()
# The new SDK uses a Client object instead of global configuration
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# ─── Mock Product Catalog (Intense Scenario) ──────────────────────────────────
CATALOG: dict[str, dict] = {
    "m3_macbook_pro": {"price": 1999.99, "in_stock": False},  # OOS
    "m2_macbook_pro": {"price": 1799.99, "in_stock": False},  # OOS
    "m1_macbook_pro": {"price": 1499.99, "in_stock": True},  # IN STOCK
    "32_inch_4k_monitor": {"price": 699.99, "in_stock": False},  # OOS
    "27_inch_4k_monitor": {"price": 499.99, "in_stock": True},  # IN STOCK
    "standing_desk": {"price": 399.99, "in_stock": True},  # IN STOCK
    "ergonomic_chair": {"price": 249.99, "in_stock": True},  # IN STOCK
    "mechanical_keyboard": {"price": 129.99, "in_stock": False},  # OOS
    "membrane_keyboard": {"price": 29.99, "in_stock": True},  # IN STOCK
    "wireless_mouse": {"price": 49.99, "in_stock": True},  # IN STOCK
}

# ─── Tool Implementations ─────────────────────────────────────────────────────


def get_item_info(item: str) -> dict:
    """Returns price and availability for a specific item from the catalog.

    Args:
        item: The requested product name.

    Returns:
        A dictionary containing item name, price, and stock status.

    Edge cases:
        Returns an error dictionary if the item is entirely missing from the catalog.
    """
    key = item.lower().replace(" ", "_").replace("-", "_")
    if key not in CATALOG:
        return {"error": f"'{item}' not found in catalog"}
    info = CATALOG[key]
    return {
        "item": key,
        "price": info["price"] if info["in_stock"] else None,
        "in_stock": info["in_stock"],
    }


def search_alternatives(item: str) -> dict:
    """Returns a list of alternative product IDs for an out-of-stock item.

    Args:
        item: The out-of-stock product name.

    Returns:
        A dictionary containing the original item and a list of suggested alternatives.

    Edge cases:
        Returns an empty list for the alternatives if no mapping exists for the item.
    """
    alt_map: dict[str, list] = {
        "m3_macbook_pro": ["m2_macbook_pro", "m1_macbook_pro"],
        "32_inch_4k_monitor": ["27_inch_4k_monitor"],
        "mechanical_keyboard": ["membrane_keyboard"],
    }
    key = item.lower().replace(" ", "_").replace("-", "_")
    alts = alt_map.get(key, [])
    return {"item": key, "suggested_alternatives": alts}


def calculate_total(items_json: str) -> dict:
    """Calculates the total cost and provides an itemized breakdown.

    Args:
        items_json: A JSON string containing an array of objects with item, quantity, and price.

    Returns:
        A dictionary containing the total cost, breakdown, and warnings if applicable.

    Edge cases:
        Returns an error dictionary if the JSON fails to parse.
        Skips items with a missing or null price (e.g., OOS items).
    """
    try:
        items = json.loads(items_json)
        total, breakdown, warnings = 0.0, [], []
        for it in items:
            price = it.get("price")
            if price is None:
                warnings.append(f"SKIPPED {it.get('item', '?')} — price unknown (OOS)")
                continue
            qty = it.get("quantity", 1)
            sub = round(price * qty, 2)
            total += sub
            breakdown.append(
                {"item": it["item"], "qty": qty, "unit_price": price, "subtotal": sub}
            )
        result: dict = {"total": round(total, 2), "breakdown": breakdown}
        if warnings:
            result["warnings"] = warnings
        return result
    except Exception as exc:
        return {"error": str(exc)}


TOOL_MAP = {
    "get_item_info": get_item_info,
    "search_alternatives": search_alternatives,
    "calculate_total": calculate_total,
}


def dispatch(name: str, args: dict) -> Any:
    """Executes a tool function by name with the provided arguments.

    Args:
        name: The name of the tool function to call.
        args: A dictionary of keyword arguments for the function.

    Returns:
        The dictionary response from the invoked tool, or an error dictionary.
    """
    fn = TOOL_MAP.get(name)
    return fn(**args) if fn else {"error": f"Unknown tool: {name}"}


# ─── Tool Declarations ────────────────────────────────────────────────────────


def _make_tools(include_search_alternatives: bool) -> list[types.Tool]:
    """Creates a list of Tool objects for the new SDK.

    Args:
        include_search_alternatives: Whether the search_alternatives tool should be available.

    Returns:
        A list containing a single types.Tool wrapping the function declarations.
    """
    decls = [
        types.FunctionDeclaration(
            name="get_item_info",
            description="Look up price and availability for an item in the product catalog",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "item": types.Schema(
                        type="STRING",
                        description="Item name, e.g. 'm3_macbook_pro'",
                    )
                },
                required=["item"],
            ),
        ),
        types.FunctionDeclaration(
            name="calculate_total",
            description=(
                "Calculate total procurement cost. "
                'items_json: JSON array of {"item": str, "quantity": int, "price": float}'
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "items_json": types.Schema(
                        type="STRING",
                        description="JSON array of {item, quantity, price} objects",
                    )
                },
                required=["items_json"],
            ),
        ),
    ]
    if include_search_alternatives:
        decls.insert(
            1,
            types.FunctionDeclaration(
                name="search_alternatives",
                description="Get alternative product names for an out-of-stock item. You must check their stock status afterward.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "item": types.Schema(
                            type="STRING",
                            description="Name of the out-of-stock item",
                        )
                    },
                    required=["item"],
                ),
            ),
        )
    return [types.Tool(function_declarations=decls)]


# ─── Stats Tracking ───────────────────────────────────────────────────────────


@dataclass
class Stats:
    """Tracks execution metrics for comparing agent performance."""

    name: str
    tool_calls: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wrong_turns: int = 0
    success: bool = False
    answer: str = ""

    @property
    def total_tokens(self) -> int:
        """Returns the sum of input and output tokens."""
        return self.input_tokens + self.output_tokens


def _accum_tokens(stats: Stats, response: Any) -> None:
    """Updates stats with token usage information from a model response.

    Args:
        stats: The Stats object to update in-place.
        response: The model response containing metadata.

    Side effects:
        Mutates the stats object token counts.
    """
    meta = getattr(response, "usage_metadata", None)
    if meta:
        stats.input_tokens += getattr(meta, "prompt_token_count", 0) or 0
        stats.output_tokens += getattr(meta, "candidates_token_count", 0) or 0


# ─── Terminal Output Style Formatters ─────────────────────────────────────────


def _extract_response_content(response: Any) -> str:
    """Formats a raw Gemini response (text and/or tool calls) into a single string.

    Args:
        response: The raw response object from the Gemini API.

    Returns:
        A concatenated string of the response text and any requested tool calls.
    """
    res_parts = []
    # Loop over all content parts returned by the model
    if response.candidates:
        for p in response.candidates[0].content.parts:
            if p.text:
                res_parts.append(p.text.strip())
            if p.function_call:
                try:
                    args = dict(p.function_call.args)
                except Exception:
                    args = str(p.function_call.args)
                res_parts.append(
                    f"ToolCall({p.function_call.name}, {json.dumps(args, default=str)})"
                )
    return " ".join(res_parts)


def _extract_tool_content(parts_back: list[types.Part]) -> str:
    """Formats tool results into a single string for display.

    Args:
        parts_back: A list of Part objects containing function responses.

    Returns:
        A formatted string describing the tool execution results.
    """
    parts = []
    for p in parts_back:
        if p.function_response:
            try:
                res = dict(p.function_response.response)
            except Exception:
                res = str(p.function_response.response)
            parts.append(
                f"ToolResult({p.function_response.name}, {json.dumps(res, default=str)})"
            )
    return " ".join(parts)


def _log_system(instruction: str) -> None:
    """Logs the initial system instruction cleanly in a grey panel.

    Args:
        instruction: The system prompt text.

    Side effects:
        Prints a formatted rich Panel to the terminal.
    """
    wrapped = textwrap.fill(instruction, width=82, subsequent_indent="        ")
    content = Text.assemble(("SYSTEM: ", "dim"), (wrapped, "dim"))

    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def _log_input(role: str, content: str) -> None:
    """Logs the prompt or tool result being sent to the model in a grey panel.

    Args:
        role: The speaker role (e.g., 'user', 'tool').
        content: The text content being sent to the model.

    Side effects:
        Prints a formatted rich Panel to the terminal.
    """
    if role == "user":
        label_style = "bold blue"
        content_style = "blue"
    else:
        label_style = "bold yellow"
        content_style = "yellow"

    indent = " " * (len(role) + 2)
    wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

    content_element = Text.assemble(
        (f"{role.upper()}: ", label_style), (wrapped, content_style)
    )

    console.print(
        Panel(
            content_element,
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def _log_response(content: str) -> None:
    """Logs the verbatim response returned from the model in a grey panel.

    Args:
        content: The formatted string response from the model.

    Side effects:
        Prints a formatted rich Panel to the terminal.
    """
    wrapped_response = textwrap.fill(content, width=82, subsequent_indent="           ")
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


# ─── Shared Tool Execution Helper ─────────────────────────────────────────────


def _run_tool_calls(response: Any, stats: Stats) -> tuple[list[types.Part], str]:
    """Extracts and executes requested tool calls from a model response.

    Args:
        response: The model response object containing potential function calls.
        stats: The Stats object to track tool invocations and wrong turns.

    Returns:
        A tuple of (list of Part objects containing tool results, optional final text).

    Side effects:
        Invokes local functions and mutates the stats object.
    """
    if not response.candidates:
        return [], ""

    parts = response.candidates[0].content.parts
    fn_calls = [
        p.function_call for p in parts if p.function_call and p.function_call.name
    ]

    if not fn_calls:
        text = " ".join(p.text for p in parts if p.text)
        return [], text

    response_parts = []
    for fc in fn_calls:
        name, args = fc.name, dict(fc.args)
        result = dispatch(name, args)
        stats.tool_calls += 1

        # An out-of-stock item is tracked as a wrong turn metric
        if isinstance(result, dict) and result.get("in_stock") is False:
            stats.wrong_turns += 1

        response_parts.append(
            types.Part.from_function_response(
                name=name,
                response={"result": json.dumps(result, default=str)},
            )
        )

    return response_parts, ""


# ─── Plan-and-Execute Agent ───────────────────────────────────────────────────


def _generate_plan(task: str, stats: Stats) -> list[str]:
    """Generates a rigid step-by-step plan assuming a perfect happy path.

    Args:
        task: The overall request string.
        stats: The Stats object tracking LLM calls.

    Returns:
        A list of strings representing the sequence of plan steps.

    Side effects:
        Makes an API call and prints the interaction.
    """
    sys_inst = (
        "You are a planning agent. Output ONLY a JSON array of step strings. "
        "Assume ALL items are perfectly in stock. Plan the direct happy path only. "
        "Do NOT include conditional steps, alternatives, or stock checking logic. "
        "Output only the JSON array — no markdown, no explanation."
    )

    prompt = f"Task: {task}\n\nOutput a JSON array of steps to complete this task."

    _log_system(sys_inst)
    _log_input("user", prompt)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=sys_inst),
    )

    stats.llm_calls += 1
    _accum_tokens(stats, response)

    raw = ""
    if response.candidates:
        raw = "".join(
            p.text for p in response.candidates[0].content.parts if p.text
        ).strip()

    _log_response(raw)

    for fence in ("```json", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence) :]
    raw = raw.rstrip("```").strip()

    try:
        plan = json.loads(raw)
        return plan if isinstance(plan, list) else []
    except json.JSONDecodeError:
        return []


def _execute_step(step: str, context: str, stats: Stats) -> str:
    """Executes a single rigid step from the plan without adapting to failure.

    Args:
        step: The current step string from the plan.
        context: The concatenated results of all prior steps.
        stats: The Stats object tracking tool calls and metrics.

    Returns:
        The text response generated by the model for this isolated step.

    Side effects:
        Makes API calls and prints chat logs.
    """
    sys_inst = (
        "You are an executor. Execute ONLY the specific step you are given. "
        "Do not handle scenarios not stated in your step. "
        "Report the result concisely."
    )

    config = types.GenerateContentConfig(
        system_instruction=sys_inst,
        tools=_make_tools(include_search_alternatives=False),
    )

    chat = client.chats.create(model=MODEL, config=config)
    prompt = f"Prior context:\n{context or '(none)'}\n\nYour step: {step}"

    _log_system(sys_inst)
    _log_input("user", prompt)

    response = chat.send_message(prompt)
    stats.llm_calls += 1
    _accum_tokens(stats, response)
    _log_response(_extract_response_content(response))

    for _ in range(5):
        parts_back, final = _run_tool_calls(response, stats)
        if final:
            return final

        tool_content = _extract_tool_content(parts_back)
        if tool_content:
            _log_input("tool", tool_content)

        response = chat.send_message(parts_back)
        stats.llm_calls += 1
        _accum_tokens(stats, response)
        _log_response(_extract_response_content(response))

    return "(step did not complete)"


def run_plan_exec(task: str, stats: Stats) -> str:
    """Executes the task using a brittle Plan-and-Execute pipeline.

    Fails when encountering out-of-stock items because it lacks the ability
    to formulate alternatives dynamically.

    Args:
        task: The overall request string.
        stats: The Stats object tracking iterations and metrics.

    Returns:
        The concatenated string of all completed step results.

    Side effects:
        Makes API calls and prints interaction headers.
    """
    console.print()
    console.print(
        "[bold cyan]-- Phase 1 — Plan -------------------------------------[/bold cyan]"
    )
    plan = _generate_plan(task, stats)

    if not plan:
        stats.answer = "Failed to generate a plan."
        return stats.answer

    console.print()
    console.print(
        "[bold cyan]-- Phase 2 — Execute ----------------------------------[/bold cyan]"
    )
    ctx_parts: list[str] = []

    for i, step in enumerate(plan, 1):
        console.print(
            f"\n[bold magenta]Executing Step {i}/{len(plan)}:[/bold magenta] {step}"
        )
        context = "\n".join(ctx_parts) or "(none)"
        result = _execute_step(step, context, stats)
        ctx_parts.append(f"Step {i} result: {result[:200]}")

    stats.answer = "\n".join(ctx_parts)
    # Success is impossible if an OOS item was hit, as P&E lacks alternatives
    stats.success = stats.wrong_turns == 0
    return stats.answer


# ─── Results Display ──────────────────────────────────────────────────────────


def print_stats(stats: Stats) -> None:
    """Prints execution metrics.

    Args:
        stats: The populated Stats object.

    Side effects:
        Outputs a formatted Table to the terminal.
    """
    table = Table(
        title="Plan-and-Execute Performance",
        show_lines=True,
        header_style="bold",
        min_width=40,
    )
    table.add_column("Metric", style="bold", min_width=20)
    table.add_column("Value", justify="right", style="cyan", min_width=10)

    table.add_row("Tool calls (steps)", str(stats.tool_calls))
    table.add_row("LLM API calls", str(stats.llm_calls))
    table.add_row("Total tokens", str(stats.total_tokens))
    table.add_row("  ↳ input tokens", f"{stats.input_tokens:,}")
    table.add_row("  ↳ output tokens", f"{stats.output_tokens:,}")

    wt = f"[red]{stats.wrong_turns}[/]" if stats.wrong_turns else "[green]0[/]"
    table.add_row("OOS hits (wrong turns)", wt)

    table.add_section()
    ok = (
        "[bold green]✓ complete total[/bold green]"
        if stats.success
        else "[bold red]✗ incomplete[/bold red]"
    )
    table.add_row("Outcome", ok)

    console.print(table)


# ─── Main ─────────────────────────────────────────────────────────────────────

TASK = (
    "Calculate the total procurement cost for a junior developer setup: "
    "1x M1 MacBook Pro, 2x 27-inch 4K monitors, 1x standing desk, "
    "1x ergonomic chair, 1x membrane keyboard, and 1x wireless mouse. "
    "Provide an itemized breakdown and the grand total."
)


def main() -> None:
    """Main entry point orchestrating the architecture execution.

    Executes a multi-layered procurement task using a Plan-and-Execute agent.

    Side effects:
        Executes API workflows and logs test summaries to the terminal.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Plan-and-Execute Agent[/bold yellow]\n"
            "[dim]A straightforward scenario where a rigid plan executes perfectly.[/dim]\n"
            "[dim]All requested items are currently IN STOCK.[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    console.print(Panel(TASK, title="[bold]Task[/bold]", border_style="dim"))
    console.print()

    # ── Plan-and-Execute ──────────────────────────────────────────────────────
    console.print(
        Rule(
            "[bold magenta]Plan-and-Execute Agent (Rigid Execution)[/bold magenta]",
            style="magenta",
        )
    )
    console.print()
    pe = Stats(name="Plan-and-Execute")
    run_plan_exec(TASK, pe)
    console.print()

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Summary[/bold yellow]", style="yellow"))
    console.print()
    print_stats(pe)
    console.print()


if __name__ == "__main__":
    main()
