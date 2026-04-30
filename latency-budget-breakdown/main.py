"""
Latency Budget Breakdown Prototype
Applied AI Course — Concept: You cannot optimize what you have not measured.
P95 matters more than P50 in production.

Pipeline: retrieve → validate → generate
Then: (retrieve ∥ validate) → generate
"""

import asyncio
import json
import os
import random
import textwrap
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from google import genai
from google.genai import types
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL = "gemini-2.5-flash"
NUM_RUNS = 20

QUERIES = [
    "What is the difference between supervised and unsupervised learning?",
    "How does the attention mechanism work in transformers?",
    "Explain gradient descent and why it converges",
    "What are vector embeddings and how are they computed?",
    "How does backpropagation calculate gradients?",
]

MOCK_DOCS = [
    "Supervised learning uses labeled data to train models that predict outputs for new inputs.",
    "Unsupervised learning finds hidden patterns or groupings in data without labels.",
    "Attention mechanisms assign learned weights to input tokens, letting models focus on relevant parts.",
    "Gradient descent minimizes a loss by iteratively stepping parameters in the negative gradient direction.",
    "Vector embeddings are dense, low-dimensional representations that capture semantic relationships.",
    "Backpropagation computes gradients of the loss with respect to each parameter using the chain rule.",
    "Neural networks are universal function approximators composed of stacked differentiable layers.",
    "Batch normalization stabilizes and accelerates training by normalizing each layer's activations.",
]

console = Console()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ── Pipeline Steps ─────────────────────────────────────────────────────────────


def retrieve(query: str) -> list[str]:
    """Simulate a vector-database retrieval with realistic I/O latency.

    Uses random.uniform to model the variance in network + index scan time
    you would see against a real embedding store. Returns 3 sampled mock docs.
    This step is CPU-cheap but I/O-bound, making it a good candidate for
    parallelism with other independent steps.
    """
    time.sleep(random.uniform(0.15, 0.45))  # model real DB lookup latency
    return random.sample(MOCK_DOCS, k=3)


async def validate(query: str, verbose: bool = False) -> dict:
    """Ask Gemini to rate the query for safety and relevance.

    This step is intentionally lightweight (max_output_tokens=60) to represent
    a fast guard-rail or input-classification call that is independent of
    document retrieval — the key insight enabling parallelism.
    Returns a dict with keys 'safety' and 'relevance', each scored 1-5.
    Falls back to {safety:5, relevance:5} on JSON parse failure.
    """
    prompt = (
        f"Rate this query for safety (1=unsafe, 5=very safe) and AI/ML relevance "
        f"(1=off-topic, 5=highly relevant).\n"
        f"Query: {query}\n"
        f'Reply ONLY with valid JSON: {{"safety": <1-5>, "relevance": <1-5>}}'
    )

    if verbose:
        _print_llm_input("validate", [{"role": "user", "content": prompt}])

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=60),
    )

    if verbose:
        _print_llm_response("validate", response.text)

    # Strip markdown code fences that some model versions wrap around JSON
    clean = response.text.strip().strip("```json").strip("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"safety": 5, "relevance": 5}


async def generate(
    query: str, docs: list[str], validation: dict, verbose: bool = False
) -> str:
    """Ask Gemini to produce a grounded 2-3 sentence answer using retrieved docs.

    This is the heaviest step in the pipeline — a full generation call with
    no output token cap. It always depends on both retrieve and validate
    completing first, so it anchors the critical path regardless of
    how earlier steps are scheduled.
    """
    context = "\n".join(f"• {d}" for d in docs)
    prompt = (
        f"You have the following reference documents:\n{context}\n\n"
        f"Answer the question in 2-3 sentences:\n{query}"
    )

    if verbose:
        _print_llm_input("generate", [{"role": "user", "content": prompt}])

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if verbose:
        _print_llm_response("generate", response.text)

    return response.text


# ── Display Helpers ────────────────────────────────────────────────────────────


def _print_llm_input(step: str, messages: list[dict]) -> None:
    """Render an outgoing prompt as a styled bright_black panel per the terminal-output-style guide.

    Each message role gets a distinct color: user=blue, assistant=green, system=dim.
    Content is word-wrapped at 82 chars to fit inside the panel padding.
    """
    elements = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            label_style, content_style = "dim", "dim"
        elif role == "user":
            label_style, content_style = "bold blue", "blue"
        else:
            label_style, content_style = "bold green", "green"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )

    console.print(
        Panel(
            Group(*elements),
            title=f"[bold bright_black]Model Input [{step}][/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def _print_llm_response(step: str, text: str) -> None:
    """Render a model reply as a styled bright_black panel per the terminal-output-style guide.

    Response body is printed in italic to visually distinguish generated text
    from surrounding terminal output.
    """
    wrapped = textwrap.fill(text.strip(), width=82, subsequent_indent="           ")
    content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))

    console.print(
        Panel(
            content,
            title=f"[bold bright_black]Model Response [{step}][/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


# ── Pipeline Runners ───────────────────────────────────────────────────────────


async def run_sequential(query: str, verbose: bool = False) -> dict[str, float]:
    """Execute retrieve → validate → generate in strict sequence, recording each step's wall time.

    Returns a dict mapping step name to elapsed seconds. The verbose flag enables
    LLM I/O display (only used for the first run of each phase to avoid flooding output).
    """
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    docs = retrieve(query)
    timings["retrieve"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    validation = await validate(query, verbose=verbose)
    timings["validate"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = await generate(query, docs, validation, verbose=verbose)
    timings["generate"] = time.perf_counter() - t0

    return timings


async def run_parallel(query: str, verbose: bool = False) -> dict[str, float]:
    """Execute retrieve and validate concurrently, then generate, recording each step's wall time.

    retrieve and validate are independent (no shared inputs), so asyncio.gather
    runs them simultaneously. Each step's individual timer measures only its own
    work — the wall-clock saving shows up in total pipeline time, not per-step numbers.
    """
    timings: dict[str, float] = {}

    async def timed_retrieve() -> list[str]:
        """Wrap retrieve in asyncio.to_thread so the blocking sleep doesn't stall the event loop."""
        t0 = time.perf_counter()
        result = await asyncio.to_thread(retrieve, query)
        timings["retrieve"] = time.perf_counter() - t0
        return result

    async def timed_validate() -> dict:
        """Wrap validate with a timer; runs as a native coroutine on the event loop."""
        t0 = time.perf_counter()
        result = await validate(query, verbose=verbose)
        timings["validate"] = time.perf_counter() - t0
        return result

    # retrieve and validate are independent — run them at the same time
    docs, validation = await asyncio.gather(timed_retrieve(), timed_validate())

    t0 = time.perf_counter()
    _ = await generate(query, docs, validation, verbose=verbose)
    timings["generate"] = time.perf_counter() - t0

    return timings


# ── Statistics ─────────────────────────────────────────────────────────────────


def compute_percentiles(values: list[float]) -> dict[str, float]:
    """Compute P50, P95, P99, and mean for a list of latency samples in seconds.

    Uses numpy for correctness on small samples (linear interpolation by default).
    Returns a dict with keys 'p50', 'p95', 'p99', 'mean'.
    """
    arr = np.array(values)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "mean": float(np.mean(arr)),
    }


def find_dominant_step(step_data: dict[str, list[float]]) -> str:
    """Return the step name with the highest P95 latency.

    P95 (not mean) is used because it reflects the tail latency that users
    actually experience in production, not the average happy path.
    """
    return max(step_data, key=lambda s: compute_percentiles(step_data[s])["p95"])


# ── Output ─────────────────────────────────────────────────────────────────────


def print_stats_table(title: str, step_data: dict[str, list[float]]) -> None:
    """Render a Rich table of P50/P95/P99/mean latencies for every pipeline step.

    Adds a TOTAL row (sum of per-step percentiles) to show the sequential budget.
    Colors encode severity: green=P50, yellow=P95, red=P99.
    """
    table = Table(title=title, box=box.ROUNDED, show_header=True, show_lines=True)
    table.add_column("Step", style="bold", min_width=12)
    table.add_column("P50 (s)", justify="center", style="green")
    table.add_column("P95 (s)", justify="center", style="yellow")
    table.add_column("P99 (s)", justify="center", style="red")
    table.add_column("Mean (s)", justify="center", style="dim")

    totals = {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}
    for step, values in step_data.items():
        stats = compute_percentiles(values)
        table.add_row(
            step,
            f"{stats['p50']:.3f}",
            f"{stats['p95']:.3f}",
            f"{stats['p99']:.3f}",
            f"{stats['mean']:.3f}",
        )
        for k in totals:
            totals[k] += stats[k]

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{totals['p50']:.3f}[/bold]",
        f"[bold]{totals['p95']:.3f}[/bold]",
        f"[bold]{totals['p99']:.3f}[/bold]",
        f"[bold]{totals['mean']:.3f}[/bold]",
    )

    console.print(table)
    console.print()


def plot_latency_breakdown(
    seq_data: dict[str, list[float]],
    par_data: dict[str, list[float]],
    filename: str = "latency_breakdown.png",
) -> None:
    """Generate and save a 4-panel figure: per-step percentiles, distributions, total comparison, speedup.

    Panel layout:
      [0,0] grouped bar: P50/P95/P99 per step (sequential)
      [0,1] box plots: raw latency distributions per step (sequential)
      [1,0] grouped bar: total pipeline latency sequential vs parallel
      [1,1] speedup bars: factor and absolute savings at each percentile
    Saves to filename at 150 dpi.
    """
    steps = list(seq_data.keys())
    pct_keys = ["p50", "p95", "p99"]
    pct_labels = ["P50", "P95", "P99"]
    colors = {"p50": "#4CAF50", "p95": "#FF9800", "p99": "#F44336"}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Latency Budget Breakdown", fontsize=16, fontweight="bold")

    # [0,0] Per-step percentiles (sequential)
    ax = axes[0, 0]
    x = np.arange(len(steps))
    width = 0.25
    for i, (pk, pl) in enumerate(zip(pct_keys, pct_labels)):
        vals = [compute_percentiles(seq_data[s])[pk] for s in steps]
        bars = ax.bar(
            x + i * width, vals, width, label=pl, color=colors[pk], alpha=0.85
        )
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.005,
                f"{v:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.set_xticks(x + width)
    ax.set_xticklabels(steps)
    ax.set_ylabel("Latency (s)")
    ax.set_title("Sequential: Per-Step Percentiles")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # [0,1] Box plots of raw distributions
    ax = axes[0, 1]
    ax.boxplot(
        [seq_data[s] for s in steps],
        labels=steps,
        patch_artist=True,
        boxprops=dict(facecolor="#2196F3", alpha=0.6),
        medianprops=dict(color="black", linewidth=2),
        flierprops=dict(marker="o", markersize=4, alpha=0.5),
    )
    ax.set_ylabel("Latency (s)")
    ax.set_title("Sequential: Latency Distributions")
    ax.grid(axis="y", alpha=0.3)

    # Compute total latency vectors for comparison
    # Sequential: all three steps sum (they ran one after another)
    seq_totals = [sum(seq_data[s][i] for s in steps) for i in range(NUM_RUNS)]
    # Parallel: wall clock = max(retrieve, validate) + generate (critical path)
    par_totals = [
        max(par_data["retrieve"][i], par_data["validate"][i]) + par_data["generate"][i]
        for i in range(NUM_RUNS)
    ]

    # [1,0] Total pipeline latency: sequential vs parallel
    ax = axes[1, 0]
    for j, (label, totals, color) in enumerate(
        [("Sequential", seq_totals, "#F44336"), ("Parallel", par_totals, "#4CAF50")]
    ):
        stats = compute_percentiles(totals)
        offsets = [j * 4 + k for k in range(3)]
        vals = [stats[pk] for pk in pct_keys]
        bars = ax.bar(offsets, vals, color=color, alpha=0.85)
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{v:.2f}s",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.set_xticks([0, 1, 2, 4, 5, 6])
    ax.set_xticklabels(pct_labels + pct_labels)
    y_max = ax.get_ylim()[1]
    ax.text(
        1, y_max * 0.94, "Sequential", ha="center", color="#F44336", fontweight="bold"
    )
    ax.text(
        5, y_max * 0.94, "Parallel", ha="center", color="#4CAF50", fontweight="bold"
    )
    ax.set_ylabel("Total Pipeline Latency (s)")
    ax.set_title("Total Latency: Sequential vs Parallel")
    ax.grid(axis="y", alpha=0.3)

    # [1,1] Speedup factors
    ax = axes[1, 1]
    seq_st = compute_percentiles(seq_totals)
    par_st = compute_percentiles(par_totals)
    speedups = [seq_st[pk] / par_st[pk] for pk in pct_keys]
    savings = [seq_st[pk] - par_st[pk] for pk in pct_keys]
    bars = ax.bar(
        pct_labels, speedups, color=[colors[pk] for pk in pct_keys], alpha=0.85
    )
    for bar, speedup, saving in zip(bars, speedups, savings):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{speedup:.2f}×\n(−{saving:.2f}s)",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.axhline(
        y=1.0, color="black", linestyle="--", alpha=0.5, label="no speedup baseline"
    )
    ax.set_ylabel("Speedup Factor (×)")
    ax.set_title("Speedup: Sequential → Parallel")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()


# ── Phase Runner ───────────────────────────────────────────────────────────────


async def run_phase(
    phase_name: str,
    runner_fn,
    dot_color_key: str,
) -> dict[str, list[float]]:
    """Run NUM_RUNS iterations of a pipeline phase and collect per-step latency lists.

    Shows the full LLM I/O exchange only for run #1 (as a live example for students).
    Remaining runs are shown as compact progress dots: green if generate < 5s,
    yellow if < 10s, red otherwise.

    Returns dict mapping 'retrieve', 'validate', 'generate' to lists of elapsed seconds.
    """
    step_data: dict[str, list[float]] = {"retrieve": [], "validate": [], "generate": []}
    queries = [QUERIES[i % len(QUERIES)] for i in range(NUM_RUNS)]

    console.print(Rule(f"[bold]{phase_name}[/bold]", style="white"))
    console.print()

    for i, query in enumerate(queries):
        run_num = i + 1
        # Only show LLM I/O panels on the first run; suppress for the remaining 19
        verbose = run_num == 1

        if verbose:
            console.print(
                f"[bold {dot_color_key}]-- Run 01 (live LLM exchange) ------[/bold {dot_color_key}]"
            )
            console.print(f"  [dim]Query:[/dim] {query}")
            console.print()

        t_wall = time.perf_counter()
        timings = await runner_fn(query, verbose=verbose)
        elapsed = time.perf_counter() - t_wall

        for step, t in timings.items():
            step_data[step].append(t)

        gen_t = timings["generate"]
        dot_color = "green" if gen_t < 5.0 else "yellow" if gen_t < 10.0 else "red"
        dot = f"[{dot_color}]o[/{dot_color}]"
        console.print(
            f"  Run #{run_num:02d}: {dot} [dim]{elapsed:.2f}s[/dim]",
            end="   ",
            highlight=False,
        )
        if run_num % 4 == 0:
            console.print()

    console.print()
    console.print()
    return step_data


# ── Main ───────────────────────────────────────────────────────────────────────


async def main() -> None:
    """Orchestrate both pipeline phases, print statistics, print comparison summary, and save plot."""
    console.print(
        Panel.fit(
            "[bold yellow]Latency Budget Breakdown[/bold yellow]\n"
            "[dim]Instrument a 3-step pipeline: retrieve → validate → generate[/dim]\n"
            f"[dim]{NUM_RUNS} runs × 2 modes (sequential, parallel) · Model: {MODEL}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Phase 1: strict sequential ordering
    seq_data = await run_phase(
        "Phase 1: Sequential  (retrieve → validate → generate)",
        run_sequential,
        dot_color_key="cyan",
    )

    print_stats_table("Sequential — Per-Step Latencies", seq_data)

    dominant_seq = find_dominant_step(seq_data)
    seq_totals = [sum(seq_data[s][i] for s in seq_data) for i in range(NUM_RUNS)]
    seq_total_stats = compute_percentiles(seq_totals)

    console.print(
        f"  [bold]Dominant step (P95):[/bold] [bold red]{dominant_seq}[/bold red]"
    )
    console.print(
        f"  [bold]Pipeline P95 (sequential):[/bold] {seq_total_stats['p95']:.3f}s"
    )
    console.print()

    # Phase 2: retrieve and validate parallelized
    par_data = await run_phase(
        "Phase 2: Parallel  (retrieve ∥ validate → generate)",
        run_parallel,
        dot_color_key="magenta",
    )

    print_stats_table("Parallel — Per-Step Latencies", par_data)

    par_totals = [
        max(par_data["retrieve"][i], par_data["validate"][i]) + par_data["generate"][i]
        for i in range(NUM_RUNS)
    ]
    par_total_stats = compute_percentiles(par_totals)
    dominant_par = find_dominant_step(par_data)

    console.print(
        f"  [bold]New bottleneck (P95):[/bold] [bold red]{dominant_par}[/bold red]"
    )
    console.print(
        f"  [bold]Pipeline P95 (parallel):[/bold] {par_total_stats['p95']:.3f}s"
    )
    console.print()

    # Final summary
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    summary = Table(
        title="Sequential vs Parallel — Total Pipeline Latency",
        show_lines=True,
    )
    summary.add_column("Metric", style="bold", min_width=8)
    summary.add_column("Sequential", justify="center", style="red")
    summary.add_column("Parallel", justify="center", style="green")
    summary.add_column("Speedup", justify="center")
    summary.add_column("Saved", justify="center")

    seq_st = compute_percentiles(seq_totals)
    par_st = compute_percentiles(par_totals)

    for label, pk in [("P50", "p50"), ("P95", "p95"), ("P99", "p99"), ("Mean", "mean")]:
        speedup = seq_st[pk] / par_st[pk]
        saved = seq_st[pk] - par_st[pk]
        speedup_str = (
            f"[green]{speedup:.2f}×[/green]"
            if speedup > 1.05
            else f"[dim]{speedup:.2f}×[/dim]"
        )
        saved_str = (
            f"[green]+{saved:.3f}s[/green]"
            if saved > 0.001
            else f"[dim]{saved:.3f}s[/dim]"
        )
        summary.add_row(
            label,
            f"{seq_st[pk]:.3f}s",
            f"{par_st[pk]:.3f}s",
            speedup_str,
            saved_str,
        )

    console.print(summary)
    console.print()

    console.print(
        f"  [bold]Sequential bottleneck:[/bold] [bold red]{dominant_seq}[/bold red]"
    )
    console.print(
        f"  [bold]Parallel bottleneck :[/bold] [bold red]{dominant_par}[/bold red]"
    )
    console.print()

    # Save the chart
    plot_latency_breakdown(seq_data, par_data)
    console.print(
        f"  [bold green]Plot saved →[/bold green] [dim]latency_breakdown.png[/dim]"
    )
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
