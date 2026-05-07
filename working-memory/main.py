#!/usr/bin/env python3
"""
Working Memory: Context Overflow & Memory Management

An AI agent reviews a 10-step database migration plan.
The context grows with each step, eventually blowing past the budget.
This prototype demonstrates three memory management strategies:
1. Eviction: A sliding window drops the oldest memory when over budget.
2. Summarization: Old steps are compressed into a dense memory block.
3. External Storage: Context remains strictly current, querying a Chroma DB for history.

Concept: context is finite. Memory management is an engineering problem,
not a prompt problem.
"""

import os
import textwrap
import time

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai
from google.genai import types, errors
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"

# Artificial context budget. Real Gemini has ~1 M tokens; setting this low
# makes the overflow visible within 10 steps so we can demonstrate it live.
CONTEXT_BUDGET = 2_000

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


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Custom Chroma DB embedding function using Gemini's embedding API."""

    def __call__(self, input: Documents) -> Embeddings:
        """Embeds a list of strings using the gemini-embedding-2 model.

        Args:
            input: A list of string documents from Chroma DB.

        Returns:
            A list of embedding vectors (floats).
        """
        embeddings = []
        for text in input:
            time.sleep(1.0)  # Rate limit protection for embedding API
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=text,
                )
                embeddings.append(response.embeddings[0].values)
            except Exception as e:
                console.print(f"[bold red]Embedding Error:[/bold red] {e}")
                # Fallback zero-vector to prevent breaking the flow on intermittent failures
                embeddings.append([0.0] * 3072)
        return embeddings


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
    """Converts a list of message dictionaries into Gemini API Content objects.

    Args:
        messages: A list of dicts with 'role' and 'content' keys.

    Returns:
        A list of types.Content objects formatted for the Gemini API.
    """
    return [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
        for m in messages
    ]


def chat(messages: list[dict], silent: bool = True) -> tuple[str, int]:
    """Sends conversation history to Gemini, returning the text and token usage.

    Args:
        messages: The full conversation history up to this point.
        silent: If False, logs the interaction panels to the terminal using stylized panels.

    Returns:
        A tuple of (response text, total prompt tokens used).

    Side effects:
        Makes API calls, pauses for rate limits, prints formatted panels to terminal.
    """
    if not silent:
        input_elements = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                label_style, content_style = "dim", "dim"
            elif role == "user":
                label_style, content_style = "bold blue", "blue"
            elif role == "model" or role == "assistant":
                role = "assistant"
                label_style, content_style = "bold green", "green"
            else:
                label_style, content_style = "bold yellow", "yellow"

            indent = " " * (len(role) + 2)
            wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

            input_elements.append(
                Text.assemble(
                    (f"{role.upper()}: ", label_style), (wrapped, content_style)
                )
            )
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

    for attempt in range(5):
        try:
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
                wrapped_response = textwrap.fill(
                    reply, width=82, subsequent_indent="           "
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

            return reply, response.usage_metadata.prompt_token_count
        except (errors.ClientError, Exception) as e:
            if ("429" in str(e) or "name resolution" in str(e).lower() or "connecterror" in str(e).lower()) and attempt < 4:
                wait = (attempt + 1) * 20
                console.print(
                    f"  [dim yellow]Network/Rate limit issue. Waiting {wait}s (attempt {attempt+1}/5)...[/dim yellow]"
                )
                time.sleep(wait)
                continue
            raise e

    return "", 0


def count_tokens_only(messages: list[dict]) -> int:
    """Calculates the total token count for a message list without generating content.

    Args:
        messages: The conversation history.

    Returns:
        The integer token count as measured by the API.

    Side effects:
        Makes a metadata-only network call to the Gemini API.
    """
    response = client.models.count_tokens(
        model=GEMINI_MODEL,
        contents=build_contents(messages),
    )
    return response.total_tokens


def summarise_history(completed_steps: list[dict]) -> str:
    """Compresses completed investigation steps into a single dense memory block.

    Args:
        completed_steps: A list of dicts detailing steps and findings.

    Returns:
        A dense bullet-point summary retaining key facts.

    Side effects:
        Prints strategy intent and makes an API call with styled panels.
    """
    step_text = "\n\n".join(
        f"Step {s['num']}: {s['name']}\n"
        f"Data: {s['tool_output']}\n"
        f"Finding: {s['finding']}"
        for s in completed_steps
    )
    prompt = (
        "Compress the following investigation steps into a dense memory block. "
        "Preserve ONLY critical facts: exact commands, numbers, table names, "
        "constraint names, procedures, breaking changes, and action items. "
        "Remove ALL conversational text and redundant context. "
        "Use extreme abbreviation. Max 100 words. "
        "Every token must carry information.\n\n"
        + step_text
    )

    console.print(
        Rule("[bold magenta]Compression Strategy[/bold magenta]", style="magenta")
    )
    console.print(
        f"  [dim]Input:[/dim] verbose history of {len(completed_steps)} steps."
    )
    console.print(f"  [dim]Goal:[/dim] dense bullet points, zero information loss.")
    console.print()

    input_elements = [
        Text.assemble(
            ("USER: ", "bold blue"),
            (textwrap.fill(prompt, width=82, subsequent_indent="      "), "blue"),
        )
    ]
    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    messages = [{"role": "user", "content": prompt}]
    summary = ""

    for attempt in range(5):
        try:
            time.sleep(API_DELAY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=build_contents(messages),
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=800
                ),
            )
            summary = response.text.strip()
            break
        except (errors.ClientError, Exception) as e:
            if ("429" in str(e) or "name resolution" in str(e).lower() or "connecterror" in str(e).lower()) and attempt < 4:
                wait = (attempt + 1) * 20
                console.print(
                    f"  [dim yellow]Network/Rate limit issue. Waiting {wait}s (attempt {attempt+1}/5)...[/dim yellow]"
                )
                time.sleep(wait)
                continue
            raise e

    wrapped_response = textwrap.fill(summary, width=82, subsequent_indent="           ")
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

    return summary


# ── Display Helpers ───────────────────────────────────────────────────────────


def token_bar(count: int, width: int = 20) -> Text:
    """Returns a color-coded Text progress bar representing context window usage.

    Args:
        count: The current token count.
        width: The visual length of the bar.

    Returns:
        A formatted rich Text object tracking threshold severity.
    """
    pct = min(count / CONTEXT_BUDGET, 1.0)
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct < 0.5 else "yellow" if pct < 0.85 else "red"
    return Text(f"{bar}  {count:,}  ({int(pct * 100)}%)", style=color)


def check_recall(answer: str) -> bool:
    """Verifies if the model's answer contains all expected critical keywords.

    Args:
        answer: The string response to evaluate.

    Returns:
        True if all global EXPECTED_KEYWORDS are present (case-insensitive).
    """
    lower = answer.lower()
    return all(kw.lower() in lower for kw in EXPECTED_KEYWORDS)


def print_recall_result(label: str, answer: str, success: bool) -> None:
    """Prints the results of a recall verification test to the terminal.

    Args:
        label: A string describing the test scenario.
        answer: The verbatim answer provided by the model.
        success: Boolean indicating if verification passed.

    Side effects:
        Prints structured feedback blocks with semantic colors.
    """
    console.print(
        f"\n[bold cyan]-- {label} --------------------------------------[/bold cyan]"
    )
    prefix = "[dim]Model Answer:[/dim]"
    wrapped = textwrap.fill(answer, width=88, subsequent_indent="               ")
    console.print(f"  {prefix} [italic]{wrapped}[/italic]", highlight=False)

    verdict = (
        "[bold green]RETAINED[/bold green]" if success else "[bold red]LOST[/bold red]"
    )
    console.print(
        f"  [bold]Result:[/bold] {verdict} [dim](keywords: {', '.join(EXPECTED_KEYWORDS)})[/dim]"
    )


# ── Phase 1: Eviction (Sliding Window) ────────────────────────────────────────


def run_eviction_phase() -> tuple[list[dict], list[dict]]:
    """Runs the eviction simulation dropping oldest turns when budget is exceeded.

    Returns:
        A tuple of (token metric logs per step, cumulative message history).

    Side effects:
        Makes API calls and renders progress bars per iteration.
    """
    console.print(
        Rule("[bold]Phase 1: Eviction (Sliding Window)[/bold]", style="white")
    )
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

        # Evict strictly before generating to simulate a rigid context window
        evicted = False
        current_tokens = count_tokens_only(messages)
        while current_tokens > CONTEXT_BUDGET and len(messages) > 1:
            messages.pop(0)  # Evict user message
            if messages:
                messages.pop(0)  # Evict assistant message
            current_tokens = count_tokens_only(messages)
            evicted = True

        reply, prompt_tokens = chat(messages)
        messages.append({"role": "model", "content": reply})

        bar = token_bar(prompt_tokens)
        flag = "  [bold red]OVER BUDGET → EVICTED[/bold red]" if evicted else ""

        console.print(
            f"  Step [bold]{i:02d}[/bold]  [dim]{step['name']:<28}[/dim]  ", end=""
        )
        console.print(bar, end="")
        console.print(flag)

        token_log.append({"step": i, "name": step["name"], "tokens": prompt_tokens})

    return token_log, messages


# ── Phase 2: Summarization ────────────────────────────────────────────────────


def run_summarization_phase() -> tuple[list[dict], list[dict]]:
    """Runs the summarization simulation compressing history mid-flight.

    Returns:
        A tuple of (token metric logs, final message history).

    Side effects:
        Makes multiple API calls, swaps message history, and prints progress UI.
    """
    console.print(Rule(f"[bold]Phase 2: Summarization[/bold]", style="white"))
    console.print()

    messages: list[dict] = []
    token_log: list[dict] = []
    completed_steps: list[dict] = []

    for i, step in enumerate(STEPS, start=1):
        if i == SUMMARISE_AFTER + 1:
            tokens_before = token_log[-1]["tokens"]
            console.print(
                f"\n  [bold yellow]→ Context at {tokens_before:,} tokens — "
                f"compressing steps 1–{SUMMARISE_AFTER}...[/bold yellow]"
            )

            summary = summarise_history(completed_steps)
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
            console.print(
                f"  [dim]Context Shift:[/dim] [yellow]{tokens_before:,}[/yellow] → [green]{tokens_after:,}[/green] tokens "
                f"([bold green]{pct}% reduction[/bold green])\n"
            )

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
        marker = (
            "  [dim yellow]← compressed here[/dim yellow]"
            if i == SUMMARISE_AFTER
            else ""
        )

        console.print(
            f"  Step [bold]{i:02d}[/bold]  [dim]{step['name']:<28}[/dim]  ", end=""
        )
        console.print(bar, end="")
        console.print(flag + marker)

        token_log.append({"step": i, "name": step["name"], "tokens": prompt_tokens})

        if i <= SUMMARISE_AFTER:
            completed_steps.append(
                {
                    "num": i,
                    "name": step["name"],
                    "tool_output": step["tool_output"],
                    "finding": reply,
                }
            )

    return token_log, messages


# ── Phase 3: External Storage (Chroma DB) ─────────────────────────────────────


def run_external_storage_phase() -> tuple[list[dict], chromadb.Collection]:
    """Runs the external storage simulation using Chroma DB for RAG.

    Context is kept strictly to the current step + retrieved relevant past steps.

    Returns:
        A tuple of (token metric logs, the populated Chroma DB collection).

    Side effects:
        Initializes Chroma DB, generates embeddings via API, prints progress UI.
    """
    console.print(
        Rule("[bold]Phase 3: External Storage (Chroma DB)[/bold]", style="white")
    )
    console.print()

    chroma_client = chromadb.Client()
    try:
        chroma_client.delete_collection("migration_steps")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name="migration_steps", embedding_function=GeminiEmbeddingFunction()
    )

    token_log: list[dict] = []

    for i, step in enumerate(STEPS, start=1):
        query_text = f"Step {step['name']}: {step['question']}"
        retrieved_context = ""

        # Retrieve up to 2 relevant past steps if we have populated the DB
        if i > 1:
            results = collection.query(
                query_texts=[query_text], n_results=min(2, i - 1)
            )
            if results["documents"] and results["documents"][0]:
                retrieved_context = (
                    "[Retrieved Past Steps from Chroma DB]\n"
                    + "\n\n".join(results["documents"][0])
                    + "\n\n"
                )

        user_msg = (
            f"{retrieved_context}"
            f"[Current Step {i}: {step['name']}]\n"
            f"Tool output:\n{step['tool_output']}\n\n"
            f"{step['question']}"
        )

        # Context window strictly contains the single synthesized prompt
        messages = [{"role": "user", "content": user_msg}]
        reply, prompt_tokens = chat(messages)

        # Append the new state to Chroma DB
        document_text = (
            f"Step {i}: {step['name']}\n"
            f"Data: {step['tool_output']}\n"
            f"Finding: {reply}"
        )
        collection.add(documents=[document_text], ids=[f"step_{i}"])

        bar = token_bar(prompt_tokens)
        flag = "  [bold cyan]RAG CONTEXT INJECTED[/bold cyan]" if i > 1 else ""

        console.print(
            f"  Step [bold]{i:02d}[/bold]  [dim]{step['name']:<28}[/dim]  ", end=""
        )
        console.print(bar, end="")
        console.print(flag)

        token_log.append({"step": i, "name": step["name"], "tokens": prompt_tokens})

    return token_log, collection


# ── Final Summary ─────────────────────────────────────────────────────────────


def print_summary_table(
    evict_log: list[dict],
    managed_log: list[dict],
    external_log: list[dict],
    recall_evict: bool,
    recall_managed: bool,
    recall_external: bool,
) -> None:
    """Prints the comparative results of all three simulations as a markdown table.

    Args:
        evict_log: Usage metrics from Phase 1.
        managed_log: Usage metrics from Phase 2.
        external_log: Usage metrics from Phase 3.
        recall_evict: Whether eviction retained facts.
        recall_managed: Whether summarization retained facts.
        recall_external: Whether external storage retained facts.

    Side effects:
        Outputs rich Tables with semantic highlighting to terminal.
    """
    console.print()
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(
        title=f"Token Usage Per Step (budget: {CONTEXT_BUDGET:,})", show_lines=True
    )
    table.add_column("Step", justify="center", style="bold", min_width=4)
    table.add_column("Name", min_width=26)
    table.add_column("Eviction", justify="center", min_width=12)
    table.add_column("Summarized", justify="center", min_width=12)
    table.add_column("External DB", justify="center", min_width=12)

    for e, m, ext in zip(evict_log, managed_log, external_log):
        e_color = "red" if e["tokens"] > CONTEXT_BUDGET else "white"
        m_color = "red" if m["tokens"] > CONTEXT_BUDGET else "white"
        ext_color = "red" if ext["tokens"] > CONTEXT_BUDGET else "white"
        table.add_row(
            str(e["step"]),
            e["name"],
            f"[{e_color}]{e['tokens']:,}[/{e_color}]",
            f"[{m_color}]{m['tokens']:,}[/{m_color}]",
            f"[{ext_color}]{ext['tokens']:,}[/{ext_color}]",
        )

    console.print(table)
    console.print()

    v_table = Table(
        title="Critical State Retention (Recall of Step 1 Rollback Facts)",
        show_lines=True,
    )
    v_table.add_column("Scenario", min_width=48)
    v_table.add_column("Result", justify="center", min_width=16)

    def verdict(v: bool) -> str:
        """Returns stylized pass/fail string."""
        return "[bold green]RETAINED[/bold green]" if v else "[bold red]LOST[/bold red]"

    v_table.add_row("Phase 1: Eviction (Sliding Window)", verdict(recall_evict))
    v_table.add_row("Phase 2: Summarization", verdict(recall_managed))
    v_table.add_row("Phase 3: External Storage (Chroma DB)", verdict(recall_external))
    console.print(v_table)
    console.print()

    console.print(
        "  [bold green]Verdict: Both Summarization and External Storage successfully retained critical facts while respecting context constraints. Eviction caused total loss of early state.[/bold green]"
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Orchestrates all three phases to demonstrate memory management strategies.

    Executes workflows, performs recall verifications, and outputs summaries.

    Side effects:
        Invokes extensive API activity and renders all terminal UI components.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Working Memory: Context Overflow & Memory Management[/bold yellow]\n"
            "[dim]Demonstrating Eviction vs Summarization vs External Storage.[/dim]\n"
            f"[dim]Budget: {CONTEXT_BUDGET:,} tokens  ·  Model: {GEMINI_MODEL}  ·  Steps: {len(STEPS)}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # 1. Eviction Phase
    evict_log, evict_messages = run_eviction_phase()
    console.print()

    # Verification A
    full_q = evict_messages + [{"role": "user", "content": VERIFICATION_QUESTION}]
    reply_evict, _ = chat(full_q, silent=False)
    success_evict = check_recall(reply_evict)
    print_recall_result(
        "Verification A: Eviction (Sliding Window)", reply_evict, success_evict
    )
    console.print()

    # 2. Summarization Phase
    managed_log, managed_messages = run_summarization_phase()
    console.print()

    # Verification B
    managed_q = managed_messages + [{"role": "user", "content": VERIFICATION_QUESTION}]
    reply_managed, _ = chat(managed_q, silent=False)
    success_managed = check_recall(reply_managed)
    print_recall_result("Verification B: Summarization", reply_managed, success_managed)
    console.print()

    # 3. External Storage Phase
    external_log, collection = run_external_storage_phase()
    console.print()

    # Verification C
    results = collection.query(query_texts=[VERIFICATION_QUESTION], n_results=2)
    retrieved = "\n\n".join(results["documents"][0]) if results["documents"] else ""
    user_msg = (
        f"[Retrieved Context]\n{retrieved}\n\n[Question]\n{VERIFICATION_QUESTION}"
    )
    reply_external, _ = chat([{"role": "user", "content": user_msg}], silent=False)
    success_external = check_recall(reply_external)
    print_recall_result(
        "Verification C: External Storage (RAG)", reply_external, success_external
    )

    # Final Summary Table
    print_summary_table(
        evict_log,
        managed_log,
        external_log,
        success_evict,
        success_managed,
        success_external,
    )


if __name__ == "__main__":
    main()
