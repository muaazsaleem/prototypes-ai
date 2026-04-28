#!/usr/bin/env python3
"""
Reflexion Prototype: Learning Within a Session
==============================================
Demonstrates Reflexion: an agentic pattern where a model attempts a task,
analyzes its failures, and uses those insights to improve in the next attempt.
This process compounds within a single session but resets between runs.
"""

import copy
import os
import re
import textwrap

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize the rich console for styled terminal output.
console = Console()

# ── API Setup ────────────────────────────────────────────────────────────────

# gemini-2.0-flash: High-performance model capable of complex reasoning and
# self-correction during the reflexion process.
MODEL = "gemini-2.0-flash"
MAX_ATTEMPTS = 3

# Attempt to initialize the GenAI client.
try:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    console.print(
        "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set."
    )
    raise SystemExit(1)

# ── Task Definition ──────────────────────────────────────────────────────────

# The task involves implementing a grading function with specific edge cases
# designed to challenge initial coding assumptions (missing keys, partial credit).
TASK_DESCRIPTION = """\
Write a Python function called grade_exam(answers, key, partial_credit=False).

Parameters:
  answers        dict mapping question_number (int) -> student_answer (str)
  key            dict mapping question_number (int) -> correct_answer (str)
  partial_credit bool (default False)

Returns a dict with EXACTLY these five keys:
  score       float  — total points earned
  percentage  float  — score / len(key) * 100, rounded to 1 decimal place
  correct     list   — question numbers with exact match (1.0 point each)
  partial     list   — question numbers with partial credit (0.5 pts each)
  missed      list   — question numbers with no credit

Grading rules:
  1. Iterate over every question in KEY (not answers) to determine credit.
  2. Exact match   : answer == correct_answer                  → 1.0 pt, add to correct
  3. Partial match : partial_credit=True AND
                     answer.strip().lower() == correct.strip().lower()
                     but NOT an exact match                    → 0.5 pt, add to partial
  4. No match      : anything else, or question missing from answers → 0.0 pt, add to missed
  5. Questions in answers but NOT in key must be IGNORED.
  6. partial list is always present (empty list when partial_credit=False).

Function signature: def grade_exam(answers, key, partial_credit=False):
Return ONLY the Python function — no explanation, no markdown fences.\
"""

# Eight test cases covering exact matches, partial credit, missing answers,
# empty input, and extra answers.
# NOTE: The test cases secretly expect descending order, forcing a first-attempt failure.
TEST_CASES = [
    (
        {1: "Paris", 2: "London", 3: "Berlin"},
        {1: "Paris", 2: "Rome", 3: "Berlin"},
        False,
        {
            "score": 2.0,
            "percentage": 66.7,
            "correct": [3, 1],
            "partial": [],
            "missed": [2],
        },
        "Basic exact match",
    ),
    (
        {1: "paris", 2: "  London  ", 3: "Berlin"},
        {1: "Paris", 2: "London", 3: "berlin"},
        True,
        {
            "score": 1.5,
            "percentage": 50.0,
            "correct": [],
            "partial": [3, 2, 1],
            "missed": [],
        },
        "Partial credit: case + whitespace",
    ),
    (
        {1: "Paris", 3: "Berlin"},
        {1: "Paris", 2: "Rome", 3: "Berlin"},
        False,
        {
            "score": 2.0,
            "percentage": 66.7,
            "correct": [3, 1],
            "partial": [],
            "missed": [2],
        },
        "Missing answer counts as missed",
    ),
    (
        {},
        {1: "Paris", 2: "Rome"},
        False,
        {
            "score": 0.0,
            "percentage": 0.0,
            "correct": [],
            "partial": [],
            "missed": [2, 1],
        },
        "Empty answers: all missed",
    ),
    (
        {1: "A", 2: "B", 3: "C"},
        {1: "A", 2: "B", 3: "C"},
        False,
        {
            "score": 3.0,
            "percentage": 100.0,
            "correct": [3, 2, 1],
            "partial": [],
            "missed": [],
        },
        "All correct",
    ),
    (
        {1: "paris", 2: "LONDON"},
        {1: "Paris", 2: "London"},
        False,
        {
            "score": 0.0,
            "percentage": 0.0,
            "correct": [],
            "partial": [],
            "missed": [2, 1],
        },
        "Case mismatch, partial_credit=False → all missed",
    ),
    (
        {1: "Paris", 99: "Extra"},
        {1: "Paris", 2: "Rome"},
        False,
        {
            "score": 1.0,
            "percentage": 50.0,
            "correct": [1],
            "partial": [],
            "missed": [2],
        },
        "Extra answer not in key is ignored",
    ),
    (
        {1: "Paris", 2: "rome", 3: "Wrong"},
        {1: "Paris", 2: "Rome", 3: "Berlin"},
        True,
        {
            "score": 1.5,
            "percentage": 50.0,
            "correct": [1],
            "partial": [2],
            "missed": [3],
        },
        "Mixed: exact + partial + missed",
    ),
]

# ── Helpers ──────────────────────────────────────────────────────────────────


def log_llm_interaction(prompt: str, response_text: str) -> None:
    """Logs the LLM interaction in standardized grey panels.

    Args:
        prompt: The raw string prompt sent to the model.
        response_text: The string response returned by the model.

    Side effects:
        Outputs formatted rich panels to the terminal.
    """
    input_elements = []
    role = "user"
    label_style = "bold blue"
    content_style = "blue"

    indent = " " * (len(role) + 2)
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent=indent)

    input_elements.append(
        Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
    )

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
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


def accuracy_bar(correct: int, total: int, width: int = 22) -> Text:
    """Generates a styled progress bar showing the percentage of passed tests.

    Args:
        correct: Number of successful test cases.
        total: Total number of test cases run.
        width: Visual width of the progress bar in characters.

    Returns:
        A rich.text.Text object containing the colored bar and percentage.
    """
    pct = correct / total if total > 0 else 0
    filled = round(pct * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct * 100)}%)", style=color)


def extract_function(raw: str) -> str:
    """Extracts raw code from a markdown-formatted response string.

    Args:
        raw: The raw text response from the model.

    Returns:
        The text stripped of surrounding markdown code fences.
    """
    raw = re.sub(r"```(?:python)?\n?", "", raw)
    return raw.replace("```", "").strip()


def evaluate(code: str) -> list[dict]:
    """Compiles the given code and executes it against the global TEST_CASES suite.

    Args:
        code: The raw Python source string to execute.

    Returns:
        A list of dictionaries describing the pass/fail result for each test.
        If compilation fails, all tests are marked as failed with the syntax error.
    """
    results = []
    namespace: dict = {}

    try:
        # Evaluate the LLM-generated string inside the isolated namespace dict
        exec(compile(code, "<generated>", "exec"), namespace)
    except Exception as exc:
        for *_, expected, label in TEST_CASES:
            results.append(
                dict(
                    label=label,
                    passed=False,
                    got=None,
                    expected=expected,
                    error=str(exc),
                )
            )
        return results

    fn = namespace.get("grade_exam")
    if fn is None:
        # Model generated valid code but used the wrong function name
        for *_, expected, label in TEST_CASES:
            results.append(
                dict(
                    label=label,
                    passed=False,
                    got=None,
                    expected=expected,
                    error="Function 'grade_exam' not found",
                )
            )
        return results

    for answers, key, partial_credit, expected, label in TEST_CASES:
        try:
            # Deepcopy prevents the generated code from secretly mutating the test suite data
            got = fn(copy.deepcopy(answers), copy.deepcopy(key), partial_credit)
            results.append(
                dict(
                    label=label,
                    passed=(got == expected),
                    got=got,
                    expected=expected,
                    error=None,
                )
            )
        except Exception as exc:
            results.append(
                dict(
                    label=label,
                    passed=False,
                    got=None,
                    expected=expected,
                    error=str(exc),
                )
            )

    return results


# ── Agent Steps ──────────────────────────────────────────────────────────────


def generate_code(reflection_notes: list[str]) -> str:
    """Prompts the LLM to write the function, injecting prior reflections if available.

    Args:
        reflection_notes: A list of previously generated failure analysis notes.

    Returns:
        The extracted Python source code.

    Side effects:
        Makes a network call to the Gemini API and logs the interaction.
    """
    if not reflection_notes:
        prompt = TASK_DESCRIPTION
    else:
        # Concat prior reflections to create cumulative memory within the session
        combined = "\n\n".join(
            f"[Reflection from attempt {i + 1}]\n{note}"
            for i, note in enumerate(reflection_notes)
        )
        prompt = (
            f"{TASK_DESCRIPTION}\n\n"
            "--- YOUR PREVIOUS REFLECTIONS (apply these fixes!) ---\n"
            f"{combined}\n"
            "------------------------------------------------------\n\n"
            "Rewrite the function addressing every point in the reflections above."
        )

    response = client.models.generate_content(model=MODEL, contents=prompt)
    response_text = response.text
    log_llm_interaction(prompt, response_text)

    return extract_function(response_text)


def generate_reflection(attempt: int, results: list[dict], code: str) -> str:
    """Prompts the LLM to diagnose bugs based on the source code and failed test outputs.

    Args:
        attempt: The current 1-based attempt number.
        results: The output from the evaluate() function containing test pass/fail states.
        code: The Python source code that caused the failures.

    Returns:
        A string containing concise analysis and instructions to fix the code.

    Side effects:
        Makes a network call to the Gemini API and logs the interaction.
    """
    failures = [r for r in results if not r["passed"]]
    failure_lines = "\n".join(
        f"  - {r['label']}: expected {r['expected']}, got {r['got']}"
        + (f"  [error: {r['error']}]" if r["error"] else "")
        for r in failures
    )

    prompt = (
        f"You wrote this Python function (attempt {attempt}):\n\n"
        f"```python\n{code}\n```\n\n"
        f"It failed these test cases:\n{failure_lines}\n\n"
        "Write a concise reflection note (3-5 bullet points) covering:\n"
        "• What specific bugs caused each failure\n"
        "• Exactly what to change in the implementation to fix each bug\n\n"
        "Be concrete — name the specific lines or logic to change. No code examples."
    )

    response = client.models.generate_content(model=MODEL, contents=prompt)
    response_text = response.text.strip()
    log_llm_interaction(prompt, response_text)

    return response_text


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    """Runs the main reflexion loop across multiple attempts and prints a summary.

    Side effects:
        Makes API calls, evaluates code, formats outputs to stdout.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Reflexion Agent: Learning Within a Session[/bold yellow]\n"
            "[dim]Agent attempts a task, reflects on failures, and improves across iterations.[/dim]\n"
            f"[dim]{MAX_ATTEMPTS} attempts  ·  {len(TEST_CASES)} tests  ·  "
            f"Task: grade_exam()  ·  Model: {MODEL}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # In-session memory state.
    reflection_notes: list[str] = []
    scores: list[int] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        console.print(
            Rule(f"[bold]Attempt {attempt} / {MAX_ATTEMPTS}[/bold]", style="white")
        )
        console.print()

        # Phase 1: Generation
        ctx_label = (
            f"using {len(reflection_notes)} prior reflections"
            if reflection_notes
            else "cold start"
        )
        console.print(
            f"[bold cyan]-- Generation ({ctx_label}) --------------------------------------[/bold cyan]"
        )
        code = generate_code(reflection_notes)
        console.print(
            f"  [dim]Model generated {len(code.splitlines())} lines of code.[/dim]"
        )

        # Phase 2: Evaluation
        console.print()
        console.print(
            "[bold magenta]-- Evaluation ------------------------------------------------[/bold magenta]"
        )
        results = evaluate(code)

        for r in results:
            dot = "[green]o[/green]" if r["passed"] else "[red]o[/red]"
            console.print(f"  {dot} [dim]{r['label']}[/dim]", highlight=False)

        passed = sum(1 for r in results if r["passed"])
        scores.append(passed)

        console.print()
        console.print(f"  Score: {accuracy_bar(passed, len(results))}")

        # Phase 3: Reflection (only if failure occurs and not the final attempt)
        if attempt < MAX_ATTEMPTS:
            failures = [r for r in results if not r["passed"]]
            if failures:
                console.print()
                console.print(
                    "[bold yellow]-- Reflection Note -------------------------------------------[/bold yellow]"
                )
                note = generate_reflection(attempt, results, code)
                reflection_notes.append(note)

                # Wrap and display the verbatim reflection notes.
                for line in note.splitlines():
                    if line.strip():
                        wrapped = textwrap.fill(
                            line.strip(), width=88, subsequent_indent="    "
                        )
                        console.print(f"  [dim]{wrapped}[/dim]")
            else:
                console.print(
                    "\n  [bold green]All tests passed! Skipping reflection.[/bold green]"
                )
                # We can stop early if perfect score achieved, or continue to show stability.
                if passed == len(TEST_CASES):
                    # Pad the scores array for the summary table if we break.
                    while len(scores) < MAX_ATTEMPTS:
                        scores.append(passed)
                    break

        console.print()

    # ── Final Summary ─────────────────────────────────────────────────────────
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Performance Improvement", show_lines=True)
    table.add_column("Iteration", style="bold", justify="center")
    table.add_column("Pass Rate", justify="center", min_width=38)
    table.add_column("Lift", justify="center", min_width=12)

    for i, score in enumerate(scores):
        bar = accuracy_bar(score, len(TEST_CASES))
        if i == 0:
            delta = "[dim]baseline[/dim]"
        else:
            diff = score - scores[i - 1]
            if diff > 0:
                delta = f"[green]+{diff}[/green]"
            elif diff < 0:
                delta = f"[red]{diff}[/red]"
            else:
                delta = "[dim]+/-0[/dim]"
        table.add_row(f"Attempt {i + 1}", bar, delta)

    console.print(table)
    console.print()

    # Final verdict logic.
    first, last = scores[0], scores[-1]
    total = len(TEST_CASES)

    if last > first:
        verdict = f"[bold green]Improved:[/bold green] {first}/{total} → {last}/{total}"
    elif last == total:
        verdict = f"[bold green]Perfect:[/bold green] Maintained {total}/{total}"
    elif last == first:
        verdict = f"[bold yellow]Static:[/bold yellow] No change at {last}/{total}"
    else:
        verdict = f"[bold red]Regressed:[/bold red] {first}/{total} → {last}/{total}"

    console.print(f"  Verdict: {verdict}")
    console.print(
        "  [dim]Concept: Reflexion is in-session learning that resets between runs.[/dim]"
    )
    console.print()


if __name__ == "__main__":
    main()
