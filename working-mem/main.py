#!/usr/bin/env python3
"""
Working Memory: Context Overflow & Memory Management

An AI agent reviews a 10-step database migration plan.
The context grows with each step, eventually blowing past the budget.
A summarisation step compresses completed steps into a dense memory block,
letting the agent stay under budget while retaining critical facts.

Concept: context is finite. Memory management is an engineering problem,
not a prompt problem.
"""

import os
import textwrap
import time

from google import genai
from google.genai import types, errors
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"

# Artificial context budget. Real Gemini has ~1 M tokens; setting this low
# makes the overflow visible within 10 steps so we can demonstrate it live.
CONTEXT_BUDGET = 4_000

# Persistent agent role, passed as a system instruction on every API call.
SYSTEM_INSTRUCTION = (
    "You are a senior database migration analyst. "
    "You receive investigation findings one step at a time. "
    "Analyse each carefully: note exact commands, constraints, numbers, "
    "and action items. You may be asked to recall any specific detail later."
)

# Summarise history after this many completed steps.
SUMMARISE_AFTER = 5

# Delay between API calls to avoid rate limits.
API_DELAY = 15.0

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ── Step Data ─────────────────────────────────────────────────────────────────

STEPS = [
    {
        "name": "Schema Snapshot",
        "tool_output": (
            "TABLE users: id INT PK, email VARCHAR(255) UNIQUE, created_at TIMESTAMP\n"
            "TABLE orders: id INT PK, user_id INT FK→users.id, total DECIMAL(10,2), status ENUM\n"
            "TABLE order_items: id INT PK, order_id INT FK→orders.id, sku VARCHAR(64), qty INT\n"
            "TABLE audit_log: id INT PK, table_name VARCHAR(64), row_id INT, changed_at TIMESTAMP\n"
            "CRITICAL CONSTRAINT: FK_ORDERS_USER (orders.user_id → users.id) ON DELETE RESTRICT\n"
            "ROLLBACK COMMAND: pg_restore -d prod snapshot_20240115_pre_migration.dump\n"
            "ROLLBACK WINDOW: 4 hours post-migration (WAL segments are purged after that)."
        ),
        "question": "Analyse this schema. What are the critical constraints and rollback procedure?",
    },
    {
        "name": "Row Count & Volume",
        "tool_output": (
            "users:        42,817,334 rows (~18 GB)\n"
            "orders:      198,441,882 rows (~87 GB)\n"
            "order_items: 612,003,910 rows (~234 GB)\n"
            "audit_log:    89,234,001 rows (~41 GB)\n"
            "Total: ~380 GB. Peak insert rate on orders: 2,400 rows/sec.\n"
            "Estimated migration at 0.5 GB/min: ~13 hours. Must run offline or use CDC."
        ),
        "question": "Given this data volume, what migration strategy is required?",
    },
    {
        "name": "Index Inventory",
        "tool_output": (
            "users: idx_users_email (UNIQUE), idx_users_created_at\n"
            "orders: idx_orders_user_id, idx_orders_status, idx_orders_created_at, "
            "idx_orders_composite (user_id, status, created_at) — BLOAT 34%\n"
            "order_items: idx_items_order_id, idx_items_sku\n"
            "MISSING: orders.total has no index but appears in 3 queries > 500 ms.\n"
            "Action: CREATE INDEX CONCURRENTLY idx_orders_total BEFORE migration."
        ),
        "question": "What index problems must be fixed before migration?",
    },
    {
        "name": "Foreign Key Audit",
        "tool_output": (
            "FK_ORDERS_USER: orders.user_id → users.id  [ENFORCED]\n"
            "FK_ITEMS_ORDER: order_items.order_id → orders.id  [ENFORCED]\n"
            "FK_AUDIT_TABLE: audit_log.row_id (polymorphic — NOT DB-enforced)\n"
            "PROBLEM: 1,247 orphaned rows in order_items with no matching order_id.\n"
            "These violate new strict FK enforcement.\n"
            "Cleanup SQL: DELETE FROM order_items WHERE order_id NOT IN (SELECT id FROM orders);"
        ),
        "question": "What FK violations exist and what cleanup SQL is required?",
    },
    {
        "name": "Stored Procedure Audit",
        "tool_output": (
            "sp_create_order      → COMPATIBLE\n"
            "sp_refund_order      → BREAKING: references orders.status ENUM; "
            "new schema uses status_code INT. Must be rewritten.\n"
            "sp_archive_old_orders→ COMPATIBLE\n"
            "sp_user_lifetime_value → COMPATIBLE\n"
            "sp_refund_order is called 800 times/hour by refund-service."
        ),
        "question": "Which stored procedures are breaking and what is the production impact?",
    },
    {
        "name": "Application Query Scan",
        "tool_output": (
            "Scanned 847 queries across 12 services.\n"
            "BREAKING: 23 queries use SELECT * from orders — new nullable columns shift ORM mappings.\n"
            "BREAKING: refund-service hard-codes column index 7 for status; new schema puts it at 9.\n"
            "WARNING: 4 queries ORDER BY orders.created_at without an index.\n"
            "Strategy: deploy application changes BEFORE schema migration via feature flags."
        ),
        "question": "What application changes are required, and in what deployment order?",
    },
    {
        "name": "Staging Test Results",
        "tool_output": (
            "Migration completed in 11h 42m (within 13h estimate).\n"
            "Errors: 3 (all in audit_log backfill — non-critical, replayable).\n"
            "sp_refund_order rewrite: VERIFIED on staging.\n"
            "Index rebuild: 2h 14m total. idx_orders_total was slowest.\n"
            "Data integrity check: PASSED. FK violations post-run: 0.\n"
            "Rollback drill: SUCCESSFUL — restore took 38 minutes."
        ),
        "question": "What did staging tests reveal? Is the migration safe to proceed?",
    },
    {
        "name": "Deployment Checklist",
        "tool_output": (
            "[ ] Notify on-call (PagerDuty: migration-oncall)\n"
            "[ ] Enable maintenance mode: feature flag FF_CHECKOUT_MAINTENANCE\n"
            "[ ] Verify snapshot_20240115_pre_migration.dump is readable\n"
            "[ ] Run orphan cleanup SQL (step 4)\n"
            "[ ] Deploy sp_refund_order rewrite\n"
            "[ ] Deploy application changes under feature flags\n"
            "[ ] Run: pg_migrate --config prod_migration.yaml\n"
            "[ ] Monitor: watch -n 5 pg_stat_activity\n"
            "[ ] Post-migration: integrity checks, enable checkout, notify stakeholders"
        ),
        "question": "What are the go/no-go criteria and the critical execution sequence?",
    },
    {
        "name": "Risk Assessment",
        "tool_output": (
            "HIGH: 13-hour window — weekend maintenance only.\n"
            "HIGH: sp_refund_order rewrite untested under production load.\n"
            "MEDIUM: 23 SELECT * queries may cause silent ORM corruption.\n"
            "LOW: audit_log backfill errors (replayable).\n"
            "ROLLBACK TRIGGER: migration exceeds 14 h OR integrity check fails.\n"
            "ROLLBACK OWNER: DBA lead (pager: +1-555-0147)."
        ),
        "question": "What are the top risks and rollback triggers?",
    },
    {
        "name": "Final Sign-Off",
        "tool_output": (
            "Approved by: Engineering Lead, DBA Lead, Product.\n"
            "Scheduled: Saturday 2024-02-03 02:00 UTC.\n"
            "Pre-migration actions (steps 3–6): all complete.\n"
            "Staging: PASSED. On-call: confirmed.\n"
            "Status: GO FOR MIGRATION."
        ),
        "question": "Confirm all critical checks are complete. Is this a go?",
    },
]

VERIFICATION_QUESTION = (
    "What is the exact rollback command and rollback time window that was documented "
    "in the initial schema analysis? Give the exact command string."
)
EXPECTED_KEYWORDS = ["pg_restore", "snapshot_20240115_pre_migration", "4 hours"]


# ── API Helpers ───────────────────────────────────────────────────────────────


def build_contents(messages: list[dict]) -> list[types.Content]:
    """Converts a list of message dictionaries into Gemini API Content objects."""
    return [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
        for m in messages
    ]


def chat(messages: list[dict], silent: bool = True) -> tuple[str, int]:
    """Sends a conversation history to Gemini and returns the model response and token usage.

    Includes retry logic for 429 Rate Limit errors. If silent is False, prints
    the formatted conversation turns and model response to the terminal.
    """
    if not silent:
        console.print(Rule("[bold blue]Model Input[/bold blue]", style="blue"))
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                label = "[bold blue]user[/bold blue]"
                wrapped = textwrap.fill(content, width=88, subsequent_indent="         ")
                console.print(f"  {label}:    [blue]{wrapped}[/blue]")
            elif role == "model":
                label = "[bold green]assistant[/bold green]"
                wrapped = textwrap.fill(content, width=88, subsequent_indent="            ")
                console.print(f"  {label}: [green]{wrapped}[/green]")

    for attempt in range(5):
        try:
            # Add delay to stay within rate limits
            time.sleep(API_DELAY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=build_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                    max_output_tokens=400,
                ),
            )
            reply = response.text.strip()
            
            if not silent:
                console.print(Rule("[bold green]Model Response[/bold green]", style="green"))
                console.print(f"[italic]{reply}[/italic]", highlight=False)
                console.print()
                
            return reply, response.usage_metadata.prompt_token_count
        except errors.ClientError as e:
            if "429" in str(e) and attempt < 4:
                wait = (attempt + 1) * 20
                console.print(f"  [dim yellow]Rate limited. Waiting {wait}s (attempt {attempt+1}/5)...[/dim yellow]")
                time.sleep(wait)
                continue
            raise e
    return "", 0


def count_tokens_only(messages: list[dict]) -> int:
    """Calculates the total token count for a list of messages without generating content."""
    response = client.models.count_tokens(
        model=GEMINI_MODEL,
        contents=build_contents(messages),
    )
    return response.total_tokens


def summarise_history(completed_steps: list[dict]) -> str:
    """Compresses completed investigation steps into a single dense memory block.

    This uses a separate LLM call with a low temperature to ensure factual
    retention. Returns the compressed string.
    """
    step_text = "\n\n".join(
        f"Step {s['num']}: {s['name']}\n"
        f"Data: {s['tool_output']}\n"
        f"Finding: {s['finding']}"
        for s in completed_steps
    )
    prompt = (
        "Compress the following investigation steps into a dense memory block. "
        "Preserve ALL critical facts: exact commands, numbers, table names, "
        "constraint names, procedures, breaking changes, and action items. "
        "No prose — dense bullet points only. Every token must carry information.\n\n"
        + step_text
    )
    
    # Show the compression request
    console.print(Rule("[bold magenta]Compression Strategy[/bold magenta]", style="magenta"))
    console.print(f"  [dim]Input:[/dim] verbose history of {len(completed_steps)} steps.")
    console.print(f"  [dim]Goal:[/dim] dense bullet points, zero information loss.")
    console.print()
    
    messages = [{"role": "user", "content": prompt}]
    
    # We use a lower temperature for summarization to keep it factual.
    summary = ""
    for attempt in range(5):
        try:
            time.sleep(API_DELAY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=build_contents(messages),
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=800),
            )
            summary = response.text.strip()
            break
        except errors.ClientError as e:
            if "429" in str(e) and attempt < 4:
                wait = (attempt + 1) * 20
                console.print(f"  [dim yellow]Rate limited. Waiting {wait}s (attempt {attempt+1}/5)...[/dim yellow]")
                time.sleep(wait)
                continue
            raise e

    console.print(Rule("[bold green]Compressed Memory Output[/bold green]", style="green"))
    console.print(f"[italic]{summary}[/italic]", highlight=False)
    console.print()
    
    return summary


# ── Display Helpers ───────────────────────────────────────────────────────────


def token_bar(count: int, width: int = 20) -> Text:
    """Returns a color-coded Text progress bar representing context window usage."""
    pct = min(count / CONTEXT_BUDGET, 1.0)
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct < 0.5 else "yellow" if pct < 0.85 else "red"
    return Text(f"{bar}  {count:,}  ({int(pct * 100)}%)", style=color)


def check_recall(answer: str) -> bool:
    """Verifies if the model's answer contains all expected critical keywords."""
    lower = answer.lower()
    return all(kw.lower() in lower for kw in EXPECTED_KEYWORDS)


def print_recall_result(label: str, answer: str, success: bool) -> None:
    """Prints the results of a recall verification test to the terminal."""
    console.print(f"\n[bold cyan]-- {label} --------------------------------------[/bold cyan]")
    prefix = "[dim]Model Answer:[/dim]"
    wrapped = textwrap.fill(answer, width=88, subsequent_indent="               ")
    console.print(f"  {prefix} [italic]{wrapped}[/italic]", highlight=False)
    
    verdict = "[bold green]RETAINED[/bold green]" if success else "[bold red]LOST[/bold red]"
    console.print(f"  [bold]Result:[/bold] {verdict} [dim](keywords: {', '.join(EXPECTED_KEYWORDS)})[/dim]")


# ── Phase 1: Naive Agent ──────────────────────────────────────────────────────


def run_naive_phase() -> tuple[list[dict], list[dict]]:
    """Runs the naive simulation where the entire conversation history is sent to the model.

    Returns a log of token usage per step and the final list of messages.
    """
    console.print(Rule("[bold]Phase 1: Naive Agent[/bold]", style="white"))
    console.print()

    messages: list[dict] = []
    token_log: list[dict] = []

    for i, step in enumerate(STEPS, start=1):
        user_msg = (
            f"[Step {i}: {step['name']}]\n"
            f"Tool output:\n{step['tool_output']}\n\n"
            f"{step['question']}"
        )
        messages.append({"role": "user", "content": user_msg})

        reply, prompt_tokens = chat(messages)
        messages.append({"role": "model", "content": reply})

        over = prompt_tokens > CONTEXT_BUDGET
        bar = token_bar(prompt_tokens)
        flag = "  [bold red]OVER BUDGET[/bold red]" if over else ""

        console.print(f"  Step [bold]{i:02d}[/bold]  [dim]{step['name']:<28}[/dim]  ", end="")
        console.print(bar, end="")
        console.print(flag)

        token_log.append({"step": i, "name": step["name"], "tokens": prompt_tokens})

    return token_log, messages


# ── Phase 2: Managed Agent ────────────────────────────────────────────────────


def run_managed_phase() -> tuple[list[dict], list[dict], int, int]:
    """Runs the managed simulation where history is compressed after a set number of steps.

    Returns a log of token usage, the final messages, and the token counts
    immediately before and after the compression event.
    """
    console.print(Rule(f"[bold]Phase 2: Managed Agent[/bold]", style="white"))
    console.print()

    messages: list[dict] = []
    token_log: list[dict] = []
    completed_steps: list[dict] = []
    tokens_before = tokens_after = 0

    for i, step in enumerate(STEPS, start=1):

        if i == SUMMARISE_AFTER + 1:
            tokens_before = token_log[-1]["tokens"]

            console.print(f"\n  [bold yellow]→ Context at {tokens_before:,} tokens — "
                          f"compressing steps 1–{SUMMARISE_AFTER}...[/bold yellow]")

            summary = summarise_history(completed_steps)

            # Swap verbose history for the compressed memory block
            messages = [
                {
                    "role": "user",
                    "content": f"[Compressed memory — steps 1–{SUMMARISE_AFTER}]\n{summary}",
                },
                {
                    "role": "model",
                    "content": "Compressed memory loaded. All critical facts from the earlier steps are retained.",
                },
            ]

            tokens_after = count_tokens_only(messages)
            saved = tokens_before - tokens_after
            pct = int(saved / tokens_before * 100) if tokens_before else 0
            console.print(f"  [dim]Context Shift:[/dim] [yellow]{tokens_before:,}[/yellow] → [green]{tokens_after:,}[/green] tokens "
                          f"([bold green]{pct}% reduction[/bold green])\n")

        user_msg = (
            f"[Step {i}: {step['name']}]\n"
            f"Tool output:\n{step['tool_output']}\n\n"
            f"{step['question']}"
        )
        messages.append({"role": "user", "content": user_msg})

        reply, prompt_tokens = chat(messages)
        messages.append({"role": "model", "content": reply})

        over = prompt_tokens > CONTEXT_BUDGET
        bar = token_bar(prompt_tokens)
        flag = "  [bold red]OVER BUDGET[/bold red]" if over else ""
        marker = "  [dim yellow]← compressed here[/dim yellow]" if i == SUMMARISE_AFTER else ""

        console.print(f"  Step [bold]{i:02d}[/bold]  [dim]{step['name']:<28}[/dim]  ", end="")
        console.print(bar, end="")
        console.print(flag + marker)

        token_log.append({"step": i, "name": step["name"], "tokens": prompt_tokens})

        if i <= SUMMARISE_AFTER:
            completed_steps.append({
                "num": i,
                "name": step["name"],
                "tool_output": step["tool_output"],
                "finding": reply,
            })

    return token_log, messages, tokens_before, tokens_after


# ── Final Summary ─────────────────────────────────────────────────────────────


def print_summary_table(
    naive_log: list[dict],
    managed_log: list[dict],
    recall_full: bool,
    recall_truncated: bool,
    recall_managed: bool,
    tokens_before: int,
    tokens_after: int,
) -> None:
    """Prints a comparison table of token usage and critical state retention."""
    console.print()
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title=f"Token Usage Per Step (budget: {CONTEXT_BUDGET:,})", show_lines=True)
    table.add_column("Step", justify="center", style="bold", min_width=4)
    table.add_column("Name", min_width=26)
    table.add_column("Naive", justify="center", min_width=12)
    table.add_column("Managed", justify="center", min_width=12)
    table.add_column("Saved", justify="center", min_width=10)

    for n, m in zip(naive_log, managed_log):
        delta = n["tokens"] - m["tokens"]
        n_color = "red" if n["tokens"] > CONTEXT_BUDGET else "white"
        m_color = "red" if m["tokens"] > CONTEXT_BUDGET else "white"
        delta_str = f"[green]−{delta:,}[/green]" if delta > 0 else f"[red]+{abs(delta):,}[/red]" if delta < 0 else "[dim]—[/dim]"
        table.add_row(
            str(n["step"]),
            n["name"],
            f"[{n_color}]{n['tokens']:,}[/{n_color}]",
            f"[{m_color}]{m['tokens']:,}[/{m_color}]",
            delta_str,
        )

    console.print(table)
    console.print()

    v_table = Table(title="Critical State Retention (Recall of Step 1 Rollback Facts)", show_lines=True)
    v_table.add_column("Scenario", min_width=48)
    v_table.add_column("Result", justify="center", min_width=16)

    def verdict(v: bool) -> str:
        return "[bold green]RETAINED[/bold green]" if v else "[bold red]LOST[/bold red]"

    v_table.add_row("Naive Agent — full history (pass)", verdict(recall_full))
    v_table.add_row("Naive Agent — history overflowed (fail)", verdict(recall_truncated))
    v_table.add_row("Managed Agent — compressed memory (pass)", verdict(recall_managed))
    console.print(v_table)
    console.print()

    if recall_managed and not recall_truncated:
        console.print("  [bold green]Verdict: Memory management preserved critical state that naive overflow destroyed.[/bold green]")
    elif recall_managed:
        console.print("  [bold green]Verdict: Managed agent successfully retained all critical state.[/bold green]")
    else:
        console.print("  [bold red]Verdict: Summarisation was too lossy — critical state not retained.[/bold red]")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Orchestrates the naive and managed phases to demonstrate context management."""
    console.print(
        Panel.fit(
            "[bold yellow]Working Memory: Context Overflow & Memory Management[/bold yellow]\n"
            "[dim]Demonstrating how summarisation solves the finite context problem.[/dim]\n"
            f"[dim]Budget: {CONTEXT_BUDGET:,} tokens  ·  Model: {GEMINI_MODEL}  ·  Steps: {len(STEPS)}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # 1. Naive Phase
    naive_log, naive_messages = run_naive_phase()
    console.print()

    # Verification A
    full_q = naive_messages + [{"role": "user", "content": VERIFICATION_QUESTION}]
    reply_full, _ = chat(full_q)
    success_full = check_recall(reply_full)
    print_recall_result("Verification A: Naive (Full Context)", reply_full, success_full)

    # Verification B (Simulated Overflow)
    # We drop the first 3 steps (6 messages) to simulate them falling out of the window.
    truncated = naive_messages[6:] + [{"role": "user", "content": VERIFICATION_QUESTION}]
    reply_truncated, _ = chat(truncated)
    success_truncated = check_recall(reply_truncated)
    print_recall_result("Verification B: Naive (Overflowed/Truncated)", reply_truncated, success_truncated)

    console.print()

    # 2. Managed Phase
    managed_log, managed_messages, t_before, t_after = run_managed_phase()
    console.print()

    # Verification C
    managed_q = managed_messages + [{"role": "user", "content": VERIFICATION_QUESTION}]
    reply_managed, _ = chat(managed_q)
    success_managed = check_recall(reply_managed)
    print_recall_result("Verification C: Managed (Compressed Memory)", reply_managed, success_managed)

    # Final Summary
    print_summary_table(
        naive_log,
        managed_log,
        success_full,
        success_truncated,
        success_managed,
        t_before,
        t_after,
    )


if __name__ == "__main__":
    main()
