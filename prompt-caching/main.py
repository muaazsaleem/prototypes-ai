#!/usr/bin/env python3
"""
Prototype: Prompt Caching — Hit Rate Economics

Three phases:
  Phase 1 — 20 calls without caching (full input token cost on every call)
  Phase 2 — 20 calls with caching   (system prompt served from cache)
  Phase 3 — Cache invalidation       (tiny prompt change forces new cache)
"""

import os
import statistics
import textwrap
import time
from dataclasses import dataclass

from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── Model and run configuration ───────────────────────────────────────────
MODEL = "gemini-2.5-flash"
NUM_RUNS = 20

# ── Gemini 2.5 Flash pricing (USD per 1 million tokens) ───────────────────
# Source: https://ai.google.dev/gemini-api/docs/models (as of 2025)
INPUT_PRICE_PER_M = 0.15  # standard (uncached) input tokens
CACHED_INPUT_PRICE_PER_M = 0.037  # cached input reads (~75 % discount)
OUTPUT_PRICE_PER_M = 0.60  # output / completion tokens
CACHE_WRITE_PRICE_PER_M = 1.00  # one-time cost to write the cache entry

console = Console()

# ── System prompt — ~2500 tokens ──────────────────────────────────────────
# This represents the reusable "fixed" part of every prompt: a rich expert
# persona with detailed domain knowledge.  In production, this could be a
# product spec, a regulatory document, or a large tool manifest.
#
# The caching insight: paying to tokenise 2500 tokens on every one of 20
# calls costs 50,000 input tokens.  Paying once to write the cache and then
# reading it cheaply costs (2500 cache-write) + (20 × 2500 cache-read)
# — at a fraction of the per-token price.
SYSTEM_PROMPT = """
You are a Principal Database Architect with 25 years of hands-on experience
designing and scaling database systems for Fortune 500 companies and high-growth
startups. You have deep expertise across relational databases (PostgreSQL, MySQL,
Oracle), NoSQL systems (MongoDB, Cassandra, DynamoDB, Redis), NewSQL solutions
(CockroachDB, Spanner), and data warehousing technologies (BigQuery, Snowflake,
Redshift).

Your knowledge encompasses the full database lifecycle: schema design, query
optimisation, indexing strategies, replication topologies, sharding approaches,
consistency models, backup and recovery, and performance monitoring. You have
personally led migrations from monolithic databases to distributed architectures,
implemented CQRS and event sourcing patterns, and designed multi-region
active-active database setups handling millions of transactions per second.

═══════════════════════════════════════════════════════
CORE DESIGN PRINCIPLES
═══════════════════════════════════════════════════════

1. Normalisation vs. Denormalisation
   Always begin with a normalised schema (3NF) to eliminate redundancy and
   maintain data integrity. Selectively denormalise only when query performance
   demands it, and document the trade-off explicitly. A denormalised table that
   saves 10 ms of query time but causes data inconsistency bugs is never worth
   it. Materialised views offer a middle ground: automatic consistency with
   pre-computed results. In PostgreSQL, use CREATE MATERIALIZED VIEW with a
   REFRESH MATERIALIZED VIEW CONCURRENTLY strategy to keep data fresh without
   blocking reads.

2. Indexing Philosophy
   Every index is a write-time tax paid for read-time savings. Index columns
   that appear in WHERE, JOIN, ORDER BY, and GROUP BY clauses, but audit index
   usage quarterly using pg_stat_user_indexes and drop any index with low
   selectivity or zero reads. Composite indexes follow the left-prefix rule;
   column order matters enormously — an index on (status, created_at) does NOT
   help a query filtering only on created_at. Partial indexes on filtered
   subsets often outperform full-table indexes at a fraction of the storage
   cost. Example: CREATE INDEX idx_active_users ON users(email) WHERE
   is_active = true.

3. Transaction Design
   Short transactions are healthy transactions. Long-running transactions hold
   locks, bloat WAL/binlog, and degrade throughput for all concurrent writers.
   Design transactions to be idempotent wherever possible — this makes retries
   safe. For distributed transactions across microservices, prefer Saga patterns
   with compensating actions over two-phase commit (2PC). 2PC is a distributed
   deadlock waiting to happen: if the coordinator fails mid-protocol, all
   participants are blocked indefinitely.

4. Replication and Consistency
   Understand what "consistency" actually means in your system. Strong
   consistency across a single-region primary-replica PostgreSQL cluster is
   achievable with synchronous_commit = on, at the cost of write latency.
   Cross-region replication is inherently eventual-consistent; design your
   application to tolerate stale reads, or route all writes and reads to the
   primary. CAP theorem is not a binary switch: most systems can tune the
   partition-tolerance vs. availability vs. consistency dial per operation type.
   READ COMMITTED is the right default isolation level for OLTP; bump to
   SERIALIZABLE only where phantom reads would cause correctness bugs.

5. Sharding and Partitioning Strategy
   Horizontal sharding by a high-cardinality key (user_id, tenant_id)
   distributes both data and query load. Avoid "hotspot" shard keys such as
   dates or monotonically increasing integer IDs — every INSERT lands on the
   same shard, creating a write hotspot. Hash sharding distributes writes
   uniformly but makes range queries expensive (you must scatter-gather across
   all shards). Range sharding enables efficient range scans but risks hotspots
   if the key distribution is skewed. PostgreSQL declarative partitioning
   (PARTITION BY RANGE / HASH / LIST) differs from application-level sharding:
   partitioning stays within one server instance and enables partition pruning;
   sharding distributes data across multiple server instances and enables
   horizontal scale-out.

6. Query Optimisation Workflow
   Always start with EXPLAIN (ANALYZE, BUFFERS) — never guess. Look for
   sequential scans on large tables, nested-loop joins on unindexed FK columns,
   and high buffer miss rates (blks_hit vs blks_read ratio). The planner's cost
   estimates are only as good as the table statistics; run ANALYZE (or enable
   autovacuum) on tables that receive heavy writes. CTE behaviour changed in
   PostgreSQL 12: CTEs are now inlined by default (the "CTE fence" is gone),
   which can change query plans dramatically if you relied on the fence to
   prevent the planner from pushing predicates into the CTE.

7. Connection Pooling and Resource Management
   A PostgreSQL connection holds approximately 5–10 MB of memory. An
   application that opens 500 direct database connections is wasting 2.5–5 GB
   of RAM on connection state alone. PgBouncer in transaction-mode pooling is
   the standard solution: it multiplexes thousands of application connections
   over a small pool of real database connections. Warning: transaction-mode
   pooling is incompatible with advisory locks, named prepared statements
   (unless you use protocol-level tracking), and session-level variables (SET
   LOCAL). Recommended pool sizing: (2 × num_cores) + effective_spindle_count.

8. Backup and Recovery Strategy
   RPO (Recovery Point Objective) and RTO (Recovery Time Objective) drive
   backup design. Logical backups via pg_dump are portable and schema-selective
   but slow to restore at scale — a 5 TB logical dump can take many hours to
   restore. Physical backups via pg_basebackup combined with continuous WAL
   archiving enable point-in-time recovery (PITR) and restore in minutes for
   large databases. Always test restores in a staging environment; a backup
   that has never been restored is a backup that might not work. Follow the
   3-2-1 rule: three copies, two different media types, one stored offsite.

9. Observability and Monitoring
   Track the four golden signals at the database level: latency (p50/p95/p99
   query time), traffic (queries-per-second broken down by query type), errors
   (connection failures, lock timeouts, deadlocks), and saturation (CPU,
   memory, disk I/O, connection pool utilisation). pg_stat_statements is
   indispensable for identifying the top N most time-consuming query patterns
   across all connections — sort by total_exec_time to find the highest
   cumulative impact, sort by mean_exec_time to find individually slow queries.
   Set slow-query logging (log_min_duration_statement) and alert on replication
   lag (pg_stat_replication.write_lag) before it becomes a crisis.

10. Anti-Patterns to Avoid
    - SELECT *: always name your columns; schema changes silently break apps.
    - ORM N+1 queries: one DB round-trip per row in a result set is a disaster
      at scale; use eager loading (JOIN FETCH, prefetch_related) instead.
    - Unbounded queries: always include LIMIT on user-facing queries; a missing
      LIMIT on a table with 100 M rows will time out or OOM the client.
    - Schema changes without versioned migrations: ALTER TABLE in production
      without a migration script creates a snowflake schema nobody understands.
    - Business logic in triggers: triggers are invisible to the application
      layer and create debugging nightmares when behaviour changes silently.
    - Over-indexing: every additional index slows INSERT/UPDATE/DELETE and
      bloats storage — only create indexes you can prove are used.
    - Bare connections without a pool: at scale, direct PostgreSQL connections
      will OOM the database server when connection count spikes.

═══════════════════════════════════════════════════════
RESPONSE FORMAT GUIDELINES
═══════════════════════════════════════════════════════

When answering questions:
  - Cite specific configuration parameters, SQL examples, or numbers.
  - Acknowledge when the correct answer depends on workload characteristics.
  - Format SQL examples in fenced code blocks.
  - Use bullet points for lists of options or trade-offs.
  - Aim for thorough but concise answers — no filler, every sentence earns
    its place.
  - Keep responses under 150 words unless the question genuinely requires more.
"""

# Modified prompt: a single sentence is reworded at the top.
# Even a small edit anywhere in the cached content forces a full cache
# recomputation — the cache key is a hash of the entire content.
MODIFIED_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "You are a Principal Database Architect with 25 years",
    "You are a Senior Database Architect with 20 years",
    1,  # replace only the first occurrence
)

# Twenty varied questions — one per API call — so each call is realistic.
USER_MESSAGES = [
    "What is the best sharding key strategy for a multi-tenant SaaS database?",
    "How do I decide between a partial index and a full B-tree index?",
    "When should I use materialised views vs. regular views?",
    "What are the trade-offs between synchronous and asynchronous replication?",
    "How do I find and kill long-running transactions in PostgreSQL?",
    "What connection pool size should I configure for a 16-core database server?",
    "Explain the CTE fence behaviour in PostgreSQL and when it matters.",
    "What is the difference between BRIN and B-tree indexes for time-series data?",
    "How should I design my backup strategy for a 10 TB PostgreSQL database?",
    "What are the signs that my database is approaching connection saturation?",
    "When does denormalisation hurt more than it helps?",
    "How do saga patterns compare to 2PC for distributed transactions?",
    "What metrics should I alert on for a production database?",
    "How do I handle schema migrations on a high-traffic table without downtime?",
    "What is partition pruning and how does it affect query planning?",
    "How do I use pg_stat_statements to identify the most expensive queries?",
    "What are the risks of storing business logic in database triggers?",
    "How do I prevent N+1 query problems when using an ORM?",
    "What is the difference between RPO and RTO in backup planning?",
    "When should I choose CockroachDB or Spanner over PostgreSQL?",
]


@dataclass
class CallResult:
    """Holds token counts and latency for a single API call."""

    run: int
    latency_s: float
    prompt_tokens: int
    cached_tokens: int
    output_tokens: int

    @property
    def uncached_tokens(self) -> int:
        """Prompt tokens that were NOT served from cache — these cost full price."""
        return self.prompt_tokens - self.cached_tokens

    @property
    def input_cost(self) -> float:
        """Dollar cost for input tokens, splitting cached and uncached rates."""
        uncached = self.uncached_tokens * INPUT_PRICE_PER_M / 1_000_000
        cached = self.cached_tokens * CACHED_INPUT_PRICE_PER_M / 1_000_000
        return uncached + cached

    @property
    def output_cost(self) -> float:
        """Dollar cost for output (completion) tokens."""
        return self.output_tokens * OUTPUT_PRICE_PER_M / 1_000_000

    @property
    def total_cost(self) -> float:
        """Combined input + output cost for this single call."""
        return self.input_cost + self.output_cost


def _display_exchange(user_msg: str, response_text: str, run: int) -> None:
    """Render one LLM input/output exchange inside grey panels."""
    # Input panel: show only the user turn (system prompt is implicit / cached)
    user_content = Text.assemble(
        ("USER: ", "bold blue"),
        (textwrap.fill(user_msg, width=82, subsequent_indent="      "), "blue"),
    )
    console.print(
        Panel(
            user_content,
            title=f"[bold bright_black]Model Input — Run #{run:02d}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    # Output panel: the model's reply
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic"),
    )
    console.print(
        Panel(
            response_content,
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def run_without_caching(client: genai.Client) -> list[CallResult]:
    """
    Execute NUM_RUNS generate_content calls with no prompt caching.

    Each call sends the full SYSTEM_PROMPT in system_instruction, so every
    call pays the full uncached input-token price for the system prompt.
    Returns one CallResult per call.
    """
    results: list[CallResult] = []

    console.print(Rule("[bold]Phase 1 — Without Caching[/bold]", style="white"))
    console.print()
    console.print(
        "[dim]Each call sends the full system prompt — no caching, full token cost every time.[/dim]"
    )
    console.print()

    for i, user_msg in enumerate(USER_MESSAGES, 1):
        start = time.perf_counter()
        response = client.models.generate_content(
            model=MODEL,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        elapsed = time.perf_counter() - start

        meta = response.usage_metadata
        result = CallResult(
            run=i,
            latency_s=elapsed,
            prompt_tokens=meta.prompt_token_count,
            cached_tokens=0,  # no caching in this phase
            output_tokens=meta.candidates_token_count,
        )
        results.append(result)

        # Show per-call progress dot — no cache so all are full-price reads
        console.print(
            f"  Run #{i:02d}: [red]o[/red] "
            f"[dim]{elapsed:.2f}s  "
            f"{meta.prompt_token_count:,} in / {meta.candidates_token_count:,} out[/dim]",
            end="   ",
            highlight=False,
        )
        if i % 4 == 0:
            console.print()

    console.print()
    console.print()

    # Show one representative exchange (last call) so students see the flow
    _display_exchange(USER_MESSAGES[-1], response.text, NUM_RUNS)

    return results


def run_with_caching(client: genai.Client) -> tuple[list[CallResult], float]:
    """
    Create a context cache from SYSTEM_PROMPT, then run NUM_RUNS calls.

    Returns a tuple of (list[CallResult], cache_write_cost_usd).  The
    cache_write_cost is the one-time charge to build the cache entry and must
    be amortised across all subsequent calls to compute true net savings.
    """
    results: list[CallResult] = []

    console.print(Rule("[bold]Phase 2 — With Caching[/bold]", style="white"))
    console.print()
    console.print(
        "[dim]System prompt is written to a cache once, then served cheaply on every call.[/dim]"
    )
    console.print()

    # Create the cache — one-time cost, paid before any generate_content call.
    console.print("[dim]Creating prompt cache ...[/dim]")
    cache_start = time.perf_counter()
    cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name="db_architect_system_prompt",
            system_instruction=SYSTEM_PROMPT,
            ttl="600s",  # keep cache alive for 10 minutes (enough for 20 calls)
        ),
    )
    cache_write_time = time.perf_counter() - cache_start
    console.print(f"[dim]Cache ready in {cache_write_time:.2f}s  → {cache.name}[/dim]")
    console.print()

    for i, user_msg in enumerate(USER_MESSAGES, 1):
        start = time.perf_counter()
        response = client.models.generate_content(
            model=MODEL,
            contents=user_msg,
            config=types.GenerateContentConfig(
                # Reference the pre-built cache; the system prompt is NOT resent.
                cached_content=cache.name,
            ),
        )
        elapsed = time.perf_counter() - start

        meta = response.usage_metadata
        # cached_content_token_count is 0 on a miss, > 0 on a hit.
        cached = meta.cached_content_token_count or 0
        is_hit = cached > 0

        result = CallResult(
            run=i,
            latency_s=elapsed,
            prompt_tokens=meta.prompt_token_count,
            cached_tokens=cached,
            output_tokens=meta.candidates_token_count,
        )
        results.append(result)

        hit_label = "[green]HIT [/green]" if is_hit else "[red]MISS[/red]"
        dot = "[green]o[/green]" if is_hit else "[red]o[/red]"
        console.print(
            f"  Run #{i:02d}: {dot} {hit_label} "
            f"[dim]{elapsed:.2f}s  "
            f"{cached:,}/{meta.prompt_token_count:,} cached[/dim]",
            end="   ",
            highlight=False,
        )
        if i % 4 == 0:
            console.print()

    console.print()
    console.print()

    # Show one representative exchange (last call) so students see the flow
    _display_exchange(USER_MESSAGES[-1], response.text, NUM_RUNS)

    # Cache write cost: priced on the number of tokens written (system prompt tokens).
    # We read the cached token count from the first successful hit.
    first_hit = next((r for r in results if r.cached_tokens > 0), None)
    cached_token_count = first_hit.cached_tokens if first_hit else 0
    cache_write_cost = cached_token_count * CACHE_WRITE_PRICE_PER_M / 1_000_000

    # Delete the cache to avoid ongoing storage charges.
    client.caches.delete(name=cache.name)

    return results, cache_write_cost


def run_cache_invalidation(client: genai.Client) -> None:
    """
    Demonstrate that modifying the system prompt invalidates the existing cache.

    Creates a cache for SYSTEM_PROMPT, verifies a cache hit, then makes a call
    with MODIFIED_SYSTEM_PROMPT using a freshly created second cache.  The point:
    even a one-sentence change forces a full cache rewrite — cache design is
    inseparable from prompt design.
    """
    console.print(Rule("[bold]Phase 3 — Cache Invalidation[/bold]", style="white"))
    console.print()
    console.print(
        "[dim]A single word changed in the system prompt forces a new cache write.[/dim]"
    )
    console.print()

    # ── Original prompt ──────────────────────────────────────────────────
    console.print(
        "[bold cyan]-- Original Prompt Cache ----------------------------------------[/bold cyan]"
    )
    original_cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name="original_prompt",
            system_instruction=SYSTEM_PROMPT,
            ttl="300s",
        ),
    )
    r1_start = time.perf_counter()
    resp1 = client.models.generate_content(
        model=MODEL,
        contents=USER_MESSAGES[0],
        config=types.GenerateContentConfig(cached_content=original_cache.name),
    )
    r1_elapsed = time.perf_counter() - r1_start
    m1 = resp1.usage_metadata
    cached1 = m1.cached_content_token_count or 0
    console.print(
        f"  Cached tokens: [green]{cached1:,}[/green] / {m1.prompt_token_count:,} total  "
        f"[dim]({r1_elapsed:.2f}s)[/dim]"
    )
    console.print()

    # ── Modified prompt — forces a new cache ─────────────────────────────
    console.print(
        "[bold magenta]-- Modified Prompt (one sentence changed at top) ----------------[/bold magenta]"
    )

    # Show a diff preview of what changed
    original_line = SYSTEM_PROMPT.strip().splitlines()[0]
    modified_line = MODIFIED_SYSTEM_PROMPT.strip().splitlines()[0]
    console.print(f"  [red]- {original_line}[/red]")
    console.print(f"  [green]+ {modified_line}[/green]")
    console.print()

    # The modified prompt cannot reuse the original cache — must pay write cost again.
    new_cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name="modified_prompt",
            system_instruction=MODIFIED_SYSTEM_PROMPT,
            ttl="300s",
        ),
    )
    r2_start = time.perf_counter()
    resp2 = client.models.generate_content(
        model=MODEL,
        contents=USER_MESSAGES[0],
        config=types.GenerateContentConfig(cached_content=new_cache.name),
    )
    r2_elapsed = time.perf_counter() - r2_start
    m2 = resp2.usage_metadata
    cached2 = m2.cached_content_token_count or 0

    console.print(
        f"  Cached tokens: [green]{cached2:,}[/green] / {m2.prompt_token_count:,} total  "
        f"[dim]({r2_elapsed:.2f}s)[/dim]"
    )

    # Extra write cost incurred purely because the prompt changed
    extra_write_cost = cached2 * CACHE_WRITE_PRICE_PER_M / 1_000_000
    console.print(
        f"\n  New cache write required: [bold]Yes[/bold] — old cache is invalid"
    )
    console.print(
        f"  Repeat cache-write cost: [yellow]${extra_write_cost:.6f}[/yellow]  "
        f"[dim](paid again for {cached2:,} tokens)[/dim]"
    )
    console.print()

    client.caches.delete(name=original_cache.name)
    client.caches.delete(name=new_cache.name)


def _phase_summary_table(
    label: str,
    results: list[CallResult],
    extra_cost: float = 0.0,
) -> Panel:
    """
    Build a Rich Panel containing a metrics table for one phase.

    extra_cost is the one-time cache-write cost; pass 0.0 for the no-cache phase.
    Returns a Panel ready to print — does not print itself.
    """
    total_prompt = sum(r.prompt_tokens for r in results)
    total_cached = sum(r.cached_tokens for r in results)
    total_output = sum(r.output_tokens for r in results)

    total_input_cost = sum(r.input_cost for r in results)
    total_output_cost = sum(r.output_cost for r in results)
    grand_total = total_input_cost + total_output_cost + extra_cost

    latencies = [r.latency_s for r in results]
    avg_lat = statistics.mean(latencies)
    p50_lat = statistics.median(latencies)
    # p95: index at 95th percentile position
    p95_lat = sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)]

    hits = sum(1 for r in results if r.cached_tokens > 0)
    hit_rate = hits / len(results) * 100

    t = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    t.add_column("Metric", style="bold", min_width=34)
    t.add_column("Value", justify="right")

    t.add_row("Total Prompt Tokens", f"{total_prompt:,}")
    t.add_row(
        "  — Cached",
        f"[green]{total_cached:,}[/green]" if total_cached else "[dim]0[/dim]",
    )
    t.add_row("  — Uncached", f"{total_prompt - total_cached:,}")
    t.add_row("Total Output Tokens", f"{total_output:,}")
    t.add_section()

    hit_color = "green" if hit_rate > 0 else "red"
    t.add_row("Cache Hit Rate", f"[{hit_color}]{hit_rate:.1f}%[/{hit_color}]")
    t.add_section()

    t.add_row("Input Cost", f"${total_input_cost:.6f}")
    t.add_row("Output Cost", f"${total_output_cost:.6f}")
    if extra_cost > 0:
        t.add_row("Cache Write Cost (one-time)", f"${extra_cost:.6f}")
    t.add_row("[bold]Total Cost[/bold]", f"[bold]${grand_total:.6f}[/bold]")
    t.add_section()

    t.add_row("Avg Latency", f"{avg_lat:.2f}s")
    t.add_row("p50 Latency", f"{p50_lat:.2f}s")
    t.add_row("p95 Latency", f"{p95_lat:.2f}s")

    return Panel(
        t,
        title=f"[bold]{label}[/bold]",
        border_style="white",
        padding=(1, 2),
    )


def print_comparison(
    no_cache: list[CallResult],
    cached: list[CallResult],
    cache_write_cost: float,
) -> None:
    """
    Print the final side-by-side summary comparing Phase 1 and Phase 2.

    Computes and displays: cost reduction percentage, token savings, and the
    latency gap between cache-miss calls (Phase 1) and cache-hit calls (Phase 2).
    """
    no_cache_total = sum(r.total_cost for r in no_cache)
    cached_total = sum(r.total_cost for r in cached) + cache_write_cost

    cost_saved = no_cache_total - cached_total
    # Guard against division by zero if no_cache_total is somehow 0
    cost_reduction_pct = (cost_saved / no_cache_total * 100) if no_cache_total else 0

    no_cache_tokens = sum(r.uncached_tokens for r in no_cache)
    cached_uncached_tokens = sum(r.uncached_tokens for r in cached)
    token_reduction_pct = (
        (1 - cached_uncached_tokens / no_cache_tokens) * 100 if no_cache_tokens else 0
    )

    no_cache_avg_lat = statistics.mean(r.latency_s for r in no_cache)
    cached_hits = [r for r in cached if r.cached_tokens > 0]
    cached_avg_lat = (
        statistics.mean(r.latency_s for r in cached_hits) if cached_hits else 0
    )
    lat_improvement_pct = (
        (1 - cached_avg_lat / no_cache_avg_lat) * 100 if no_cache_avg_lat else 0
    )

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    t = Table(show_header=True, header_style="bold", padding=(0, 2), show_lines=True)
    t.add_column("Metric", style="bold", min_width=30)
    t.add_column("No Caching", justify="center")
    t.add_column("With Caching", justify="center")
    t.add_column("Delta", justify="center")

    t.add_row(
        "Total Cost (20 calls)",
        f"${no_cache_total:.6f}",
        f"${cached_total:.6f}",
        f"[green]-{cost_reduction_pct:.1f}%[/green]",
    )
    t.add_row(
        "Uncached Input Tokens",
        f"{no_cache_tokens:,}",
        f"{cached_uncached_tokens:,}",
        f"[green]-{token_reduction_pct:.1f}%[/green]",
    )
    t.add_row(
        "Avg Latency (per call)",
        f"{no_cache_avg_lat:.2f}s",
        f"{cached_avg_lat:.2f}s",
        (
            f"[green]-{lat_improvement_pct:.1f}%[/green]"
            if lat_improvement_pct > 0
            else f"[yellow]{lat_improvement_pct:.1f}%[/yellow]"
        ),
    )
    t.add_row(
        "Cache Hit Rate",
        "[red]0.0%[/red]",
        "[green]100.0%[/green]",
        "[green]+100.0pp[/green]",
    )
    t.add_section()
    t.add_row(
        "[bold]Net Savings[/bold]",
        "—",
        "—",
        f"[bold green]${cost_saved:.6f}[/bold green]",
    )

    console.print(t)
    console.print()

    # Verdict
    verdict_color = "green" if cost_saved > 0 else "red"
    console.print(
        f"  Cost reduction:  [{verdict_color}]{cost_reduction_pct:.1f}%[/{verdict_color}]  "
        f"[dim](saving ${cost_saved:.6f} across {NUM_RUNS} calls)[/dim]"
    )
    console.print(
        f"  Latency speedup: [green]{lat_improvement_pct:.1f}%[/green]  "
        f"[dim]({no_cache_avg_lat:.2f}s → {cached_avg_lat:.2f}s avg per call)[/dim]"
    )
    console.print()


def main() -> None:
    """Entry point: validates env, runs all three phases, prints comparison."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        raise SystemExit(1)

    client = genai.Client(api_key=api_key)

    # ── Opening header ────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold yellow]Prompt Caching — Hit Rate Economics[/bold yellow]\n"
            "[dim]Cost and latency impact of prompt caching with Gemini 2.5 Flash.[/dim]\n"
            f"[dim]{NUM_RUNS} calls × 3 phases: no cache / with cache / invalidation[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # ── Phase 1: No caching ───────────────────────────────────────────────
    no_cache_results = run_without_caching(client)
    console.print(_phase_summary_table("Phase 1 — No Caching", no_cache_results))

    # ── Phase 2: With caching ─────────────────────────────────────────────
    cached_results, cache_write_cost = run_with_caching(client)
    console.print(
        _phase_summary_table("Phase 2 — With Caching", cached_results, cache_write_cost)
    )

    # ── Final comparison ──────────────────────────────────────────────────
    print_comparison(no_cache_results, cached_results, cache_write_cost)

    # ── Phase 3: Cache invalidation ───────────────────────────────────────
    run_cache_invalidation(client)


if __name__ == "__main__":
    main()
