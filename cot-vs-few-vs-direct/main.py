import os
import time
import textwrap
from google import genai
import matplotlib.pyplot as plt
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Configure Gemini Client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL_NAME = "gemini-2.5-flash"

console = Console()

# Benchmark Questions
BENCHMARK_DATA = [
    {
        "question": "Sally has 3 brothers. Each brother has 2 sisters. How many sisters does Sally have?",
        "answer": "1",
    },
    {
        "question": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? (Answer in dollars, e.g., 0.05)",
        "answer": "0.05",
    },
    {
        "question": "A farmer has 17 sheep and all but 9 die. How many are left?",
        "answer": "9",
    },
    {
        "question": "In a race, if you pass the person in second place, what place are you in?",
        "answer": "second",
    },
    {
        "question": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets? (Answer in minutes)",
        "answer": "5",
    },
]

# Few-Shot Examples for reasoning-based prompting
FEW_SHOT_EXAMPLES = """
Example 1:
Question: If I have 3 apples and I give 2 to my friend, but then my friend gives me 1 back, how many apples do I have?
Thought: 
1. Start with 3 apples.
2. Give 2 away: 3 - 2 = 1 apple remaining.
3. Friend gives 1 back: 1 + 1 = 2 apples.
Answer: 2

Example 2:
Question: How many legs does a spider have?
Thought:
1. Spiders are arachnids.
2. Arachnids typically have 8 legs.
Answer: 8

Example 3:
Question: What is 15 * 4?
Thought:
1. 15 * 2 is 30.
2. 30 * 2 is 60.
Answer: 60
"""


def get_gemini_response(prompt):
    """Sends a prompt to Gemini and returns the response text and token counts.

    Utilizes the google-genai SDK. Returns a tuple of (text, prompt_tokens, candidate_tokens).
    """
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    usage = response.usage_metadata
    return response.text, usage.prompt_token_count, usage.candidates_token_count


def evaluate_accuracy(response_text, correct_answer):
    """Checks if the correct answer string is present in the LLM response.

    Performs a case-insensitive search. Strips basic punctuation from both to
    improve match reliability.
    """
    cleaned_response = response_text.lower().replace(".", "").replace(",", "")
    cleaned_answer = correct_answer.lower().replace(".", "").replace(",", "")
    return cleaned_answer in cleaned_response


def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Generates a visual progress bar for accuracy display."""
    pct = correct / total
    filled = round(pct * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def run_benchmark():
    """Executes the benchmark across three prompting strategies and collects metrics.

    Iterates through Direct, Zero-Shot CoT, and Few-Shot CoT strategies.
    Outputs real-time progress and returns results for analysis.
    """
    results = {
        "Direct": {"accuracy": 0, "tokens": 0, "count": 0},
        "Zero-Shot CoT": {"accuracy": 0, "tokens": 0, "count": 0},
        "Few-Shot CoT": {"accuracy": 0, "tokens": 0, "count": 0},
    }

    strategies = [
        (
            "Direct",
            "Answer the following question directly with just the final answer: {question}",
            "cyan",
        ),
        (
            "Zero-Shot CoT",
            "Answer the following question. Think step-by-step and then provide the final answer as 'Answer: <value>': {question}",
            "magenta",
        ),
        (
            "Few-Shot CoT",
            f"Answer the following question. Think step-by-step and then provide the final answer as 'Answer: <value>'.\n\n{FEW_SHOT_EXAMPLES}\n\nQuestion: {{question}}",
            "yellow",
        ),
    ]

    console.print(
        Panel.fit(
            f"[bold yellow]Prompting Strategy Benchmark[/bold yellow]\n"
            f"[dim]Comparing Direct, Zero-Shot CoT, and Few-Shot CoT performance.[/dim]\n"
            f"[dim]Model: {MODEL_NAME} | Questions: {len(BENCHMARK_DATA)}[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    for name, template, color in strategies:
        console.print(
            f"[bold {color}]-- {name} --------------------------------------[/bold {color}]"
        )
        total_correct = 0
        total_tokens = 0

        for i, item in enumerate(BENCHMARK_DATA, 1):
            prompt = template.format(question=item["question"])

            # Model Input Block
            wrapped_input = textwrap.fill(prompt, width=82, subsequent_indent="      ")
            input_content = Text.assemble(
                ("USER: ", "bold blue"), (wrapped_input, "blue")
            )
            console.print(
                Panel(
                    input_content,
                    title="[bold bright_black]Model Input[/bold bright_black]",
                    border_style="bright_black",
                    padding=(1, 2),
                )
            )

            start_time = time.time()
            response, p_tokens, c_tokens = get_gemini_response(prompt)
            elapsed = time.time() - start_time
            total_tokens += p_tokens + c_tokens

            is_correct = evaluate_accuracy(response, item["answer"])
            if is_correct:
                total_correct += 1

            # Model Response Block
            wrapped_response = textwrap.fill(
                response.strip(), width=82, subsequent_indent="           "
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

            dot = "[green]o[/green]" if is_correct else "[red]x[/red]"
            console.print(
                f"  [dim]Run #{i:02d}:[/dim] {dot} [dim]{elapsed:4.1f}s | {p_tokens + c_tokens} tokens[/dim]",
                highlight=False,
            )
            console.print()

        results[name]["accuracy"] = (total_correct / len(BENCHMARK_DATA)) * 100
        results[name]["total_correct"] = total_correct
        results[name]["tokens"] = total_tokens
        results[name]["count"] = len(BENCHMARK_DATA)
        console.print()

    return results


def plot_results(results):
    """Generates and saves a performance plot comparing strategies.

    Displays accuracy and token usage on a dual-axis chart.
    """
    names = list(results.keys())
    accuracies = [results[n]["accuracy"] for n in names]
    tokens = [results[n]["tokens"] for n in names]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = "tab:blue"
    ax1.set_xlabel("Strategy")
    ax1.set_ylabel("Accuracy (%)", color=color)
    ax1.bar(names, accuracies, color=color, alpha=0.6, label="Accuracy")
    ax1.tick_params(axis="y", labelcolor=color)
    ax1.set_ylim(0, 110)

    # Secondary axis for token count
    ax2 = ax1.twinx()
    color = "tab:red"
    ax2.set_ylabel("Total Tokens Used", color=color)
    ax2.plot(names, tokens, color=color, marker="o", label="Token Cost")
    ax2.tick_params(axis="y", labelcolor=color)

    plt.title(f"Accuracy vs. Token Cost ({MODEL_NAME})")
    fig.tight_layout()
    plt.savefig("benchmark_results.png")


def display_stats(results):
    """Displays a summary table and final verdict based on benchmark data.

    Calculates efficiency as accuracy points per 1000 tokens.
    """
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Benchmark Results", show_lines=True)
    table.add_column("Strategy", style="bold", min_width=15)
    table.add_column("Accuracy", justify="center")
    table.add_column("Total Tokens", justify="center", style="dim")
    table.add_column("Avg Tokens/Query", justify="center", style="dim")

    for name, data in results.items():
        avg_tokens = data["tokens"] / data["count"]
        acc_bar = accuracy_bar(data["total_correct"], data["count"])

        table.add_row(
            name,
            acc_bar,
            str(data["tokens"]),
            f"{avg_tokens:.1f}",
        )

    console.print(table)
    console.print()

    # Evaluate best performing strategies
    best_acc = max(results.values(), key=lambda x: x["accuracy"])["accuracy"]
    best_strategies = [n for n, d in results.items() if d["accuracy"] == best_acc]

    # Calculate token efficiency
    efficiency = {
        n: (d["accuracy"] / (d["tokens"] / 1000)) if d["tokens"] > 0 else 0
        for n, d in results.items()
    }
    most_efficient = max(efficiency, key=efficiency.get)

    verdict_text = (
        f"Highest Accuracy: [green]{', '.join(best_strategies)} ({best_acc:.1f}%)[/green]\n"
        f"Most Efficient:   [cyan]{most_efficient}[/cyan]"
    )

    console.print(
        Panel.fit(
            verdict_text,
            title="[bold]Verdict[/bold]",
            border_style="green",
        )
    )
    console.print()
    console.print(f"[dim]Plot saved to benchmark_results.png[/dim]")


if __name__ == "__main__":
    results = run_benchmark()
    display_stats(results)
    plot_results(results)
