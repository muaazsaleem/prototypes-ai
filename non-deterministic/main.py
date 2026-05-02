import os
import time
import textwrap
from collections import Counter
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()


def get_gemini_client():
    """Initializes and returns the Gemini API client using the environment variable.

    Returns:
        An authenticated genai.Client instance.

    Side effects:
        Reads GEMINI_API_KEY from the environment.

    Edge cases / gotchas:
        Raises ValueError if GEMINI_API_KEY is not found.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set."
        )
        raise ValueError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def call_gemini(client, prompt, model_name="gemini-2.5-flash"):
    """Generates a text response from the Gemini model for a given prompt.

    Args:
        client: The authenticated genai.Client instance.
        prompt: The string text to send to the model.
        model_name: The Gemini model identifier to use.

    Returns:
        The stripped string response from the model, or an error string if the call fails.

    Side effects:
        Makes a synchronous network request to the Google API.

    Edge cases / gotchas:
        Returns an error string starting with 'Error:' on API failures rather than throwing.
    """
    try:
        # using a consistent temperature to isolate the effect of prompt constraints
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def display_exchange(prompt, response):
    """Prints the prompt and model response to the console using rich panels.

    Args:
        prompt: The string text sent to the model.
        response: The string text returned by the model.

    Side effects:
        Writes styled output to stdout via the global rich Console.
    """
    input_elements = []
    messages = [{"role": "user", "content": prompt}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        label_style = "bold blue"
        content_style = "blue"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
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
        response, width=82, subsequent_indent="           "
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


def run_experiment(client, name, prompt, iterations=20):
    """Executes a prompt multiple times and collects all responses.

    Args:
        client: The authenticated genai.Client instance.
        name: Display label for the experiment run.
        prompt: The string text to send to the model.
        iterations: Number of total times to run the prompt.

    Returns:
        A list of string responses from the model.

    Side effects:
        Makes multiple synchronous network requests.
        Writes progress indicators and a sample exchange to stdout.
    """
    console.print(
        f"[bold cyan]-- {name} --------------------------------------[/bold cyan]"
    )
    console.print(f"[dim]Running {iterations} iterations...[/dim]")

    responses = []

    sample_response = call_gemini(client, prompt)
    display_exchange(prompt, sample_response)
    responses.append(sample_response)

    console.print("  [dim]Collecting remaining responses:[/dim]")

    # 1st run was the sample, start loop at run 2 (index 1)
    for i in range(1, iterations):
        run_num = i + 1
        start_time = time.time()
        resp = call_gemini(client, prompt)
        responses.append(resp)
        elapsed = time.time() - start_time

        # determine if error occurred to switch dot color
        passed = not resp.startswith("Error:")
        dot = "[green]o[/green]" if passed else "[red]o[/red]"

        console.print(
            f"  Run #{run_num:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )
        if run_num % 4 == 0:
            console.print()

    # Ensure final newline if it didn't end cleanly
    if iterations % 4 != 0:
        console.print()
    console.print()
    return responses


def calculate_metrics(responses):
    """Calculates unique response count and consistency percentage from a list of outputs.

    Args:
        responses: A list of string model outputs.

    Returns:
        A dict containing 'unique_count' (int), 'consistency_pct' (float), and 'total' (int).

    Edge cases / gotchas:
        Assumes responses list is non-empty; will raise IndexError on empty list.
    """
    total = len(responses)
    counts = Counter(responses)
    unique_count = len(counts)
    most_common_count = counts.most_common(1)[0][1]
    consistency_pct = (most_common_count / total) * 100

    return {
        "unique_count": unique_count,
        "consistency_pct": consistency_pct,
        "total": total,
    }


def log_responses_to_file(filename, prompt, responses):
    """Writes the prompt and collected responses to a Markdown file.

    Args:
        filename: The string path to the output Markdown file.
        prompt: The original prompt sent to the model.
        responses: A list of string model outputs.

    Side effects:
        Writes to the local filesystem, overwriting the file if it exists.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Prompt\n\n```text\n{prompt}\n```\n\n")
        f.write("# Responses\n\n")
        for i, resp in enumerate(responses, 1):
            f.write(f"## Run {i}\n\n```text\n{resp}\n```\n\n")


def main():
    """Orchestrates the prototype by running both strategies and printing the comparison table.

    Side effects:
        Configures API, makes network calls, writes log files, and writes formatted tables to stdout.
    """
    client = get_gemini_client()

    console.print(
        Panel.fit(
            "[bold yellow]LLM Variance & Determinism Prototype[/bold yellow]\n"
            "[dim]Demonstrating the impact of output constraints on response variance.[/dim]\n"
            "[dim]Model: gemini-2.5-flash | 20 runs per strategy[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    base_review = "The new smartphone is amazing, the camera quality is top-notch but the battery life is a bit disappointing. I love the design though!"

    unconstrained_prompt = f"Extract the sentiment and key entities from this customer review: '{base_review}'"

    constrained_prompt = (
        f"Extract the sentiment and key entities from this customer review: '{base_review}'\n"
        "Output only a JSON object with the keys 'sentiment' and 'entities'. "
        "'sentiment' should be a string (Positive, Negative, or Mixed). "
        "'entities' should be a list of strings."
    )

    unconstrained_res = run_experiment(
        client, "Strategy A: Unconstrained Prompt", unconstrained_prompt
    )
    log_responses_to_file(
        "output-unconstrained.md", unconstrained_prompt, unconstrained_res
    )
    metrics_a = calculate_metrics(unconstrained_res)

    constrained_res = run_experiment(
        client, "Strategy B: Constrained (JSON) Prompt", constrained_prompt
    )
    log_responses_to_file("output-constrained.md", constrained_prompt, constrained_res)
    metrics_b = calculate_metrics(constrained_res)

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Variance Comparison", show_lines=True)
    table.add_column("Metric", style="bold", min_width=24)
    table.add_column("Strategy A (Unconstrained)", justify="center", style="cyan")
    table.add_column("Strategy B (Constrained)", justify="center", style="magenta")
    table.add_column("Delta / Impact", justify="center")

    delta_unique = metrics_b["unique_count"] - metrics_a["unique_count"]
    delta_unique_str = (
        f"[green]{delta_unique}[/green]"
        if delta_unique < 0
        else f"[red]+{delta_unique}[/red]" if delta_unique > 0 else "[dim]+/-0[/dim]"
    )

    table.add_row(
        "Unique Responses",
        str(metrics_a["unique_count"]),
        str(metrics_b["unique_count"]),
        delta_unique_str,
    )

    delta_cons = metrics_b["consistency_pct"] - metrics_a["consistency_pct"]
    delta_cons_str = (
        f"[green]+{delta_cons:.1f}%[/green]"
        if delta_cons > 0
        else f"[red]{delta_cons:.1f}%[/red]" if delta_cons < 0 else "[dim]+/-0[/dim]"
    )

    table.add_row(
        "Consistency Score (%)",
        f"{metrics_a['consistency_pct']:.1f}%",
        f"{metrics_b['consistency_pct']:.1f}%",
        delta_cons_str,
    )

    console.print(table)
    console.print()

    if metrics_b["consistency_pct"] > metrics_a["consistency_pct"]:
        verdict = "[bold green]VERDICT: Output constraints significantly reduced variance and improved determinism.[/bold green]"
    elif metrics_b["consistency_pct"] < metrics_a["consistency_pct"]:
        verdict = "[bold red]VERDICT: Constraints unexpectedly increased variance in this specific run.[/bold red]"
    else:
        verdict = "[bold yellow]VERDICT: No significant change in variance was observed.[/bold yellow]"

    console.print(verdict)
    console.print()


if __name__ == "__main__":
    main()
