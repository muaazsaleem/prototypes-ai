"""
Prototype: Chain-of-Thought vs. Direct Answer
==============================================
Demonstrates that asking a model to "think step by step" is a reliability
lever — not just a stylistic choice.

For each multi-step reasoning problem we run two prompt strategies 10 times:
  • Direct  — "Answer in one short sentence. Do not show working."
  • CoT     — "Think step by step, then state your final answer."

We score every response, aggregate accuracy across all runs, and display
a side-by-side comparison so the *distribution* — not just a single lucky
or unlucky example — is visible.

Concept: CoT forces the model to commit to intermediate steps, which
catches compounding errors before they reach the final answer.
"""

import os
import time

from google import genai
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

MODEL_NAME = "gemini-2.5-flash"
RUNS_PER_PROBLEM = 8

# ── Problems ───────────────────────────────────────────────────────────────────
# Each problem has a clear numeric answer that is easy to verify automatically.
# The "wrong_answer" field documents the intuitive but incorrect response —
# exactly what a model under direct prompting often produces.

PROBLEMS = [
    {
        "title": "Spatial Navigation (Grid)",
        "question": (
            "Start at origin (0,0) facing North (+Y direction). "
            "Move forward 3 units. Turn right 90 degrees. Move forward 2 units. "
            "Turn right 90 degrees. Move forward 5 units. "
            "Turn left 90 degrees. Move backward 2 units. "
            "What are your exact final (X,Y) coordinates? Format as (X, Y)."
        ),
        "correct_answers": ["(0, -2)", "(0,-2)"],
        "wrong_answer": "(4, -2) or (2, 2) (loses track of current heading before moving)",
        "explanation": "Start(0,0) N -> Fwd 3 to (0,3). Right to E -> Fwd 2 to (2,3). Right to S -> Fwd 5 to (2,-2). Left to E -> Back 2 (moving West) to (0,-2).",
    },
    {
        "title": "Relational Logic (Family Tree)",
        "question": (
            "Alice is the sister of Bob. Bob is the father of Charlie. "
            "Charlie is the brother of Diana. Diana is the mother of Eve. "
            "What is the exact biological relationship of Alice to Eve?"
        ),
        "correct_answers": ["great-aunt", "great aunt", "grand-aunt", "grand aunt"],
        "wrong_answer": "Aunt or Grandmother (skips a generational layer)",
        "explanation": "Bob is Diana's father. Alice is Bob's sister, making her Diana's aunt. Diana is Eve's mother, making Alice Eve's great-aunt.",
    },
    {
        "title": "Temporal Scheduling",
        "question": (
            "Five speakers (A, B, C, D, E) present one after another. "
            "E must speak exactly third. B must speak immediately after D. "
            "D cannot be the first speaker. C must speak at some point before A. "
            "What is the exact sequence of the 5 speakers from first to last? Format as a comma-separated list."
        ),
        "correct_answers": ["c, a, e, d, b", "c,a,e,d,b"],
        "wrong_answer": "C, D, B, E, A (violates E being third or D being first)",
        "explanation": "E is 3rd (_ _ E _ _). DB is a block, can't be 1-2 (D not 1st), so must be 4-5 (_ _ E D B). C before A fills 1 and 2 (C A E D B).",
    },
    {
        "title": "Inventory State Tracking",
        "question": (
            "An empty box is given to you. You put in an Apple, a Banana, and a Carrot. "
            "You remove the Apple and add a Date. You remove the Carrot and put the Apple back in. "
            "You swap the Banana for an Eggplant. Finally, you take out the Date. "
            "List exactly the items currently in the box."
        ),
        "correct_answers": ["apple, eggplant", "eggplant, apple", "apple and eggplant", "eggplant and apple"],
        "wrong_answer": "Apple, Banana, Date (fails to apply all state changes sequentially)",
        "explanation": "Add A,B,C -> [A,B,C]. Rem A, Add D -> [B,C,D]. Rem C, Add A -> [A,B,D]. Swap B for E -> [A,D,E]. Rem D -> [A,E].",
    },
    {
        "title": "Logic Puzzle (Truth-Tellers)",
        "question": (
            "There are three boxes: X, Y, and Z. Exactly one contains a diamond. "
            "Box X says: 'The diamond is in Box Y.' "
            "Box Y says: 'The diamond is not in Box Y.' "
            "Box Z says: 'The diamond is not in Box X.' "
            "Exactly one box's statement is true. Which box contains the diamond? "
            "Answer with the exact phrase 'Box X', 'Box Y', or 'Box Z'."
        ),
        "correct_answers": ["box x"],
        "wrong_answer": "Box Y or Z (fails to evaluate the statements against all possible states)",
        "explanation": "If the diamond is in X: X is false, Y is true, Z is false. This yields exactly one true statement, satisfying the condition.",
    },
]

# ── Prompt strategies ──────────────────────────────────────────────────────────

def direct_prompt(question: str) -> str:
    """No reasoning — just give the answer."""
    return (
        f"{question}\n\n"
        "Answer in one short sentence only. Do not show any working or reasoning."
    )


def cot_prompt(question: str) -> str:
    """Explicit chain-of-thought before the answer."""
    return (
        f"{question}\n\n"
        "Think step by step. Show each step of your reasoning clearly, "
        "then state your final answer on the last line."
    )


# ── API helpers ────────────────────────────────────────────────────────────────

def ask(prompt: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text.strip()


def is_correct(response: str, correct_answers: list[str]) -> bool:
    """Return True if any accepted answer string appears in the model response."""
    response_lower = response.lower()
    return any(ans.lower() in response_lower for ans in correct_answers)


# ── Display helpers ────────────────────────────────────────────────────────────

def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Render a filled/empty block bar with colour based on accuracy."""
    pct = correct / total
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def run_strategy(prompt_fn, label: str, problem: dict) -> tuple[list[bool], list[float]]:
    """Run one prompt strategy RUNS_PER_PROBLEM times and return (pass/fail list, time list)."""
    results = []
    times = []
    for run in range(1, RUNS_PER_PROBLEM + 1):
        start_t = time.perf_counter()
        response = ask(prompt_fn(problem["question"]))
        elapsed = time.perf_counter() - start_t
        
        passed = is_correct(response, problem["correct_answers"])
        results.append(passed)
        times.append(elapsed)
        
        dot = "[green]●[/green]" if passed else "[red]●[/red]"
        console.print(f"  {label} #{run:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]", end="   ", highlight=False)
        if run % 4 == 0:
            console.print()
        time.sleep(0.4)  # gentle on rate limits
    if RUNS_PER_PROBLEM % 4 != 0:
        console.print()
    return results, times


# ── Main ───────────────────────────────────────────────────────────────────────

def run_demo():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY not set. Add it to a .env file.")
        raise SystemExit(1)

    console.print(
        Panel.fit(
            "[bold yellow]Chain-of-Thought vs. Direct Answer[/bold yellow]\n"
            "[dim]Comparison of performance and latency across multiple reasoning problems.[/dim]\n"
            f"[dim]{RUNS_PER_PROBLEM} runs × 2 strategies × {len(PROBLEMS)} problems[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    summary: list[dict] = []

    for i, problem in enumerate(PROBLEMS, start=1):
        console.print(Rule(f"[bold]Problem {i} / {len(PROBLEMS)}: {problem['title']}[/bold]", style="white"))
        console.print(f"[bold]Q:[/bold] {problem['question']}")
        console.print(f"[bold]Correct answer:[/bold] [green]{problem['correct_answers'][0]}[/green]")
        console.print(f"[bold]Common wrong answer:[/bold] [red]{problem['wrong_answer']}[/red]")
        console.print(f"[dim]{problem['explanation']}[/dim]\n")

        console.print("[bold cyan]── Direct prompts ──────────────────────────[/bold cyan]")
        direct_results, direct_times = run_strategy(direct_prompt, "Direct", problem)
        console.print()

        console.print("[bold magenta]── Chain-of-Thought prompts ─────────────────[/bold magenta]")
        cot_results, cot_times = run_strategy(cot_prompt, "CoT   ", problem)
        console.print()

        direct_acc = sum(direct_results)
        cot_acc = sum(cot_results)
        direct_avg_t = sum(direct_times) / len(direct_times)
        cot_avg_t = sum(cot_times) / len(cot_times)

        table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
        table.add_column("Strategy", width=10)
        table.add_column("Score", width=6, justify="center")
        table.add_column("Avg Time", width=10, justify="right")
        table.add_column("Distribution (filled = correct)")

        table.add_row(
            "[cyan]Direct[/cyan]",
            f"{direct_acc}/{RUNS_PER_PROBLEM}",
            f"{direct_avg_t:.2f}s",
            accuracy_bar(direct_acc, RUNS_PER_PROBLEM),
        )
        table.add_row(
            "[magenta]CoT[/magenta]",
            f"{cot_acc}/{RUNS_PER_PROBLEM}",
            f"{cot_avg_t:.2f}s",
            accuracy_bar(cot_acc, RUNS_PER_PROBLEM),
        )

        console.print(table)
        console.print()

        summary.append({
            "title": problem["title"],
            "direct": direct_acc,
            "cot": cot_acc,
            "direct_t": direct_avg_t,
            "cot_t": cot_avg_t
        })

    # ── Overall summary ────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))

    total_runs = RUNS_PER_PROBLEM * len(PROBLEMS)
    summary_table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    summary_table.add_column("Problem", min_width=24)
    summary_table.add_column("Direct", justify="center")
    summary_table.add_column("CoT", justify="center")
    summary_table.add_column("Avg T (D/C)", justify="center")
    summary_table.add_column("CoT lift", justify="center")
    summary_table.add_column("Distribution")

    total_direct = total_cot = 0
    total_direct_t = total_cot_t = 0
    for row in summary:
        lift = row["cot"] - row["direct"]
        if lift > 0:
            lift_str = f"[green]+{lift}[/green]"
        elif lift < 0:
            lift_str = f"[red]{lift}[/red]"
        else:
            lift_str = "[dim]±0[/dim]"

        # Mini side-by-side bar for the summary
        d_bar = "█" * row["direct"] + "░" * (RUNS_PER_PROBLEM - row["direct"])
        c_bar = "█" * row["cot"] + "░" * (RUNS_PER_PROBLEM - row["cot"])
        dist = Text()
        dist.append(f"D:{d_bar}", style="cyan")
        dist.append("  ")
        dist.append(f"C:{c_bar}", style="magenta")

        summary_table.add_row(
            row["title"],
            f"{row['direct']}/{RUNS_PER_PROBLEM}",
            f"{row['cot']}/{RUNS_PER_PROBLEM}",
            f"{row['direct_t']:.1f}s / {row['cot_t']:.1f}s",
            lift_str,
            dist,
        )
        total_direct += row["direct"]
        total_cot += row["cot"]
        total_direct_t += row["direct_t"]
        total_cot_t += row["cot_t"]

    summary_table.add_section()
    total_lift = total_cot - total_direct
    lift_color = "green" if total_lift > 0 else "red" if total_lift < 0 else "dim"
    avg_direct_t = total_direct_t / len(PROBLEMS)
    avg_cot_t = total_cot_t / len(PROBLEMS)

    summary_table.add_row(
        "[bold]TOTAL / AVG[/bold]",
        f"[bold]{total_direct}/{total_runs}[/bold]",
        f"[bold]{total_cot}/{total_runs}[/bold]",
        f"[bold]{avg_direct_t:.1f}s / {avg_cot_t:.1f}s[/bold]",
        f"[bold {lift_color}]{'+' if total_lift > 0 else ''}{total_lift}[/bold {lift_color}]",
        "",
    )

    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    run_demo()
