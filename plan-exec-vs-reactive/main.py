#!/usr/bin/env python3
"""
Prototype: Plan-and-Execute vs Reactive (ReAct) Agent

This prototype demonstrates two different agentic architectures handling an intense,
multi-layered procurement task. The catalog features cascading failures (out-of-stock items
whose alternatives are ALSO out of stock). 

ReAct adapts dynamically through an intense loop of discovery and correction. 
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
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()
# The new SDK uses a Client object instead of global configuration
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# ─── Mock Product Catalog (Intense Scenario) ──────────────────────────────────
CATALOG: dict[str, dict] = {
    "m3_macbook_pro": {"price": 1999.99, "in_stock": False},      # OOS
    "m2_macbook_pro": {"price": 1799.99, "in_stock": False},      # OOS
    "m1_macbook_pro": {"price": 1499.99, "in_stock": True},       # IN STOCK
    "32_inch_4k_monitor": {"price": 699.99, "in_stock": False},   # OOS
    "27_inch_4k_monitor": {"price": 499.99, "in_stock": True},    # IN STOCK
    "standing_desk": {"price": 399.99, "in_stock": True},         # IN STOCK
    "ergonomic_chair": {"price": 249.99, "in_stock": True},       # IN STOCK
    "mechanical_keyboard": {"price": 129.99, "in_stock": False},  # OOS
    "membrane_keyboard": {"price": 29.99, "in_stock": True},      # IN STOCK
    "wireless_mouse": {"price": 49.99, "in_stock": True},         # IN STOCK
}

# ─── Tool Implementations ─────────────────────────────────────────────────────


def get_item_info(item: str) -> dict:
    """Returns price and availability for a specific item from the catalog."""
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
    """Returns a list of alternative product IDs for an out-of-stock item."""
    alt_map: dict[str, list] = {
        "m3_macbook_pro": ["m2_macbook_pro", "m1_macbook_pro"],
        "32_inch_4k_monitor": ["27_inch_4k_monitor"],
        "mechanical_keyboard": ["membrane_keyboard"],
    }
    key = item.lower().replace(" ", "_").replace("-", "_")
    alts = alt_map.get(key, [])
    return {"item": key, "suggested_alternatives": alts}


def calculate_total(items_json: str) -> dict:
    """Calculates the total cost and provides an itemized breakdown."""
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
    """Executes a tool function by name with the provided arguments."""
    fn = TOOL_MAP.get(name)
    return fn(**args) if fn else {"error": f"Unknown tool: {name}"}


# ─── Tool Declarations ────────────────────────────────────────────────────────


def _make_tools(include_search_alternatives: bool) -> list[types.Tool]:
    """Creates a list of Tool objects for the new SDK."""
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
    """Updates stats with token usage information from a model response."""
    meta = getattr(response, "usage_metadata", None)
    if meta:
        stats.input_tokens += getattr(meta, "prompt_token_count", 0) or 0
        stats.output_tokens += getattr(meta, "candidates_token_count", 0) or 0


# ─── Terminal Output Style Formatters ─────────────────────────────────────────


def _extract_response_content(response: Any) -> str:
    """Formats a raw Gemini response (text and/or tool calls) into a single string."""
    res_parts = []
    # The new SDK response.candidates[0].content.parts is the structure
    if response.candidates:
        for p in response.candidates[0].content.parts:
            if p.text:
                res_parts.append(p.text.strip())
            if p.function_call:
                try:
                    args = dict(p.function_call.args)
                except Exception:
                    args = str(p.function_call.args)
                res_parts.append(f"ToolCall({p.function_call.name}, {json.dumps(args, default=str)})")
    return " ".join(res_parts)


def _extract_tool_content(parts_back: list[types.Part]) -> str:
    """Formats tool results into a single string for display."""
    parts = []
    for p in parts_back:
        if p.function_response:
            try:
                res = dict(p.function_response.response)
            except Exception:
                res = str(p.function_response.response)
            parts.append(f"ToolResult({p.function_response.name}, {json.dumps(res, default=str)})")
    return " ".join(parts)


def _log_system(instruction: str) -> None:
    """Logs the initial system instruction cleanly."""
    console.print(Rule("[dim]System Instruction[/dim]", style="dim"))
    wrapped = textwrap.fill(instruction, width=88, subsequent_indent="           ")
    console.print(f"  [dim]system[/dim]:  [dim]{wrapped}[/dim]")
    console.print()


def _log_input(role: str, content: str) -> None:
    """Logs the prompt or tool result being sent TO the model."""
    console.print(Rule(f"[bold blue]Model Input ({role})[/bold blue]", style="blue"))
    if role == "user":
        label = "[bold blue]user[/bold blue]"
        color = "blue"
    else:
        label = "[bold yellow]tool[/bold yellow]"
        color = "yellow"
    
    wrapped = textwrap.fill(content, width=88, subsequent_indent="            ")
    console.print(f"  {label}:    [{color}]{wrapped}[/{color}]")
    console.print()


def _log_response(content: str) -> None:
    """Logs the verbatim response returned FROM the model."""
    console.print(Rule("[bold green]Model Response[/bold green]", style="green"))
    console.print(f"[italic]{content}[/italic]", highlight=False)
    console.print()


# ─── Shared Tool Execution Helper ─────────────────────────────────────────────


def _run_tool_calls(response: Any, stats: Stats) -> tuple[list[types.Part], str]:
    """Extracts and executes tool calls from a model response."""
    if not response.candidates:
        return [], ""
        
    parts = response.candidates[0].content.parts
    fn_calls = [p.function_call for p in parts if p.function_call and p.function_call.name]

    if not fn_calls:
        text = " ".join(p.text for p in parts if p.text)
        return [], text

    response_parts = []
    for fc in fn_calls:
        name, args = fc.name, dict(fc.args)
        result = dispatch(name, args)
        stats.tool_calls += 1

        # An OOS result is a "wrong turn"
        if isinstance(result, dict) and result.get("in_stock") is False:
            stats.wrong_turns += 1

        response_parts.append(
            types.Part.from_function_response(
                name=name,
                response={"result": json.dumps(result, default=str)},
            )
        )

    return response_parts, ""


# ─── ReAct Agent ──────────────────────────────────────────────────────────────


def run_react(task: str, stats: Stats) -> str:
    """Executes the task using the highly adaptive ReAct architecture."""
    sys_inst = (
        "You are a procurement assistant. Use get_item_info to look up prices. "
        "If an item is out of stock, call search_alternatives to get substitute names, "
        "then look up those substitutes until you find one that is IN STOCK. "
        "Use the cheapest available option. Finish with calculate_total."
    )
    
    config = types.GenerateContentConfig(
        system_instruction=sys_inst,
        tools=_make_tools(include_search_alternatives=True)
    )
    
    # The new SDK uses client.chats.create
    chat = client.chats.create(model=MODEL, config=config)
    
    _log_system(sys_inst)
    _log_input("user", task)
    
    response = chat.send_message(task)
    stats.llm_calls += 1
    _accum_tokens(stats, response)
    _log_response(_extract_response_content(response))

    for _ in range(30):
        parts_back, final = _run_tool_calls(response, stats)
        if final:
            stats.answer = final
            stats.success = True
            break
            
        tool_content = _extract_tool_content(parts_back)
        _log_input("tool", tool_content)
        
        response = chat.send_message(parts_back)
        stats.llm_calls += 1
        _accum_tokens(stats, response)
        _log_response(_extract_response_content(response))

    return stats.answer


# ─── Plan-and-Execute Agent ───────────────────────────────────────────────────


def _generate_plan(task: str, stats: Stats) -> list[str]:
    """Generates a rigid step-by-step plan assuming everything goes perfectly."""
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
        config=types.GenerateContentConfig(system_instruction=sys_inst)
    )
    
    stats.llm_calls += 1
    _accum_tokens(stats, response)
    
    raw = ""
    if response.candidates:
        raw = "".join(p.text for p in response.candidates[0].content.parts if p.text).strip()
    
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
    """Executes a single step from the pre-defined plan. Fails silently on OOS."""
    sys_inst = (
        "You are an executor. Execute ONLY the specific step you are given. "
        "Do not handle scenarios not stated in your step. "
        "Report the result concisely."
    )
    
    config = types.GenerateContentConfig(
        system_instruction=sys_inst,
        tools=_make_tools(include_search_alternatives=False)
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
    """Executes the rigid plan linearly, accumulating errors along the way."""
    console.print()
    console.print("[bold cyan]-- Phase 1 — Plan -------------------------------------[/bold cyan]")
    plan = _generate_plan(task, stats)

    if not plan:
        stats.answer = "Failed to generate a plan."
        return stats.answer

    console.print()
    console.print("[bold cyan]-- Phase 2 — Execute ----------------------------------[/bold cyan]")
    ctx_parts: list[str] = []

    for i, step in enumerate(plan, 1):
        console.print(f"\n[bold magenta]Executing Step {i}/{len(plan)}:[/bold magenta] {step}")
        context = "\n".join(ctx_parts) or "(none)"
        result = _execute_step(step, context, stats)
        ctx_parts.append(f"Step {i} result: {result[:200]}")

    stats.answer = "\n".join(ctx_parts)
    # Success is impossible if OOS was hit, as P&E lacks alternatives
    stats.success = stats.wrong_turns == 0
    return stats.answer


# ─── Results Display ──────────────────────────────────────────────────────────


def _cmp(a: int, b: int, lower_is_better: bool = True) -> tuple[str, str]:
    """Returns a colored string tuple for comparing two numeric metrics."""
    if a == b:
        return str(a), str(b)
    if (a < b) == lower_is_better:
        return f"[green]{a}[/]", f"[red]{b}[/]"
    return f"[red]{a}[/]", f"[green]{b}[/]"


def print_comparison(react: Stats, pe: Stats) -> None:
    """Prints a comparison table of metrics between both agent architectures."""
    table = Table(
        title="ReAct vs Plan-and-Execute",
        show_lines=True,
        header_style="bold",
        min_width=64,
    )
    table.add_column("Metric", style="bold", min_width=26)
    table.add_column("ReAct", justify="right", style="cyan", min_width=14)
    table.add_column("Plan-and-Execute", justify="right", style="magenta", min_width=18)

    r_tc, p_tc = _cmp(react.tool_calls, pe.tool_calls)
    table.add_row("Tool calls (steps)", r_tc, p_tc)

    r_lc, p_lc = _cmp(react.llm_calls, pe.llm_calls)
    table.add_row("LLM API calls", r_lc, p_lc)

    r_tt, p_tt = _cmp(react.total_tokens, pe.total_tokens)
    table.add_row("Total tokens", r_tt, p_tt)
    table.add_row("  ↳ input tokens", f"{react.input_tokens:,}", f"{pe.input_tokens:,}")
    table.add_row("  ↳ output tokens", f"{react.output_tokens:,}", f"{pe.output_tokens:,}")

    r_wt = f"[yellow]{react.wrong_turns}[/]" if react.wrong_turns else "[green]0[/]"
    p_wt = f"[red]{pe.wrong_turns}[/]" if pe.wrong_turns else "[green]0[/]"
    table.add_row("OOS hits (wrong turns)", r_wt, p_wt)

    table.add_section()
    r_ok = (
        "[bold green]✓ complete total[/bold green]"
        if react.success
        else "[bold red]✗ incomplete[/bold red]"
    )
    p_ok = (
        "[bold green]✓ complete total[/bold green]"
        if pe.success
        else "[bold red]✗ incomplete[/bold red]"
    )
    table.add_row("Outcome", r_ok, p_ok)

    console.print(table)


# ─── Main ─────────────────────────────────────────────────────────────────────

TASK = (
    "Calculate the total procurement cost for a senior developer setup: "
    "1x M3 MacBook Pro, 2x 32-inch 4K monitors, 1x standing desk, "
    "1x ergonomic chair, 1x mechanical keyboard, and 1x wireless mouse. "
    "Provide an itemized breakdown and the grand total."
)


def main() -> None:
    """Main entry point for the intense agent architecture comparison demo."""
    console.print(
        Panel.fit(
            "[bold yellow]Plan-and-Execute vs ReAct Agent[/bold yellow]\n"
            "[dim]A cascading failure scenario forcing high-intensity adaptation.[/dim]\n"
            "[dim]3 of 6 requested items are OOS. 1 alternative is ALSO OOS.[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    console.print(Panel(TASK, title="[bold]Task[/bold]", border_style="dim"))
    console.print()

    # ── ReAct ─────────────────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]ReAct Agent (Intense Adaptation Loop)[/bold cyan]", style="cyan"))
    console.print()
    react = Stats(name="ReAct")
    run_react(TASK, react)
    console.print()

    # ── Plan-and-Execute ──────────────────────────────────────────────────────
    console.print(Rule("[bold magenta]Plan-and-Execute Agent (Rigid Execution)[/bold magenta]", style="magenta"))
    console.print()
    pe = Stats(name="Plan-and-Execute")
    run_plan_exec(TASK, pe)
    console.print()

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()
    print_comparison(react, pe)
    console.print()


if __name__ == "__main__":
    main()
