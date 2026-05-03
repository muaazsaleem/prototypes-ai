import os
import time
import textwrap
import google.generativeai as genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# Configuration
MODEL_NAME = "gemini-2.5-flash"
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

LOOSE_TOOLS = [
    genai.types.FunctionDeclaration(
        name="get_weather_current",
        description="Get weather information for a location.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="get_weather_forecast",
        description="Get weather data for a city.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="get_weather_history",
        description="Fetch weather records for a specific area.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
]

TIGHT_TOOLS = [
    genai.types.FunctionDeclaration(
        name="get_weather_current",
        description="Get CURRENT, REAL-TIME weather conditions for a specific location. Use only for queries about 'now', 'today', or current status.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="get_weather_forecast",
        description="Get FUTURE weather predictions and forecasts. Use only for queries about 'tomorrow', 'next week', 'upcoming', or future dates.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="get_weather_history",
        description="Fetch HISTORICAL weather records from the past. Use only for queries about yesterday, last year, or specific past dates.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "The city name."}
            },
            "required": ["location"],
        },
    ),
]

QUERIES = [
    # Current (17)
    ("How is the weather in Tokyo right now?", "get_weather_current"),
    ("Is it raining in London at the moment?", "get_weather_current"),
    ("Current temperature in Paris?", "get_weather_current"),
    ("Show me today's weather for NYC.", "get_weather_current"),
    ("What's the humidity like in Berlin today?", "get_weather_current"),
    ("Tell me the weather for Sydney now.", "get_weather_current"),
    ("Status of weather in Mumbai.", "get_weather_current"),
    ("Is it sunny in Madrid today?", "get_weather_current"),
    ("Check weather for Rome.", "get_weather_current"),
    ("What's the wind speed in Chicago right now?", "get_weather_current"),
    ("Weather report for Seattle currently.", "get_weather_current"),
    ("Give me the current weather in Toronto.", "get_weather_current"),
    ("Current conditions in Moscow.", "get_weather_current"),
    ("Is there snow in Oslo today?", "get_weather_current"),
    ("Weather update for Cape Town.", "get_weather_current"),
    ("Current sky condition in Seoul.", "get_weather_current"),
    ("How hot is it in Dubai now?", "get_weather_current"),
    # Forecast (17)
    ("What will the weather be like tomorrow in London?", "get_weather_forecast"),
    ("Will it rain next Tuesday in Paris?", "get_weather_forecast"),
    ("Forecast for Berlin for the coming weekend.", "get_weather_forecast"),
    ("Is it going to snow tomorrow in NYC?", "get_weather_forecast"),
    ("Weather prediction for Tokyo next week.", "get_weather_forecast"),
    ("Give me the 5-day forecast for Sydney.", "get_weather_forecast"),
    ("How's the weather looking for Madrid on Friday?", "get_weather_forecast"),
    ("Will the sun be out tomorrow in Rome?", "get_weather_forecast"),
    ("Upcoming weather for Chicago.", "get_weather_forecast"),
    ("Forecast for Seattle next Monday.", "get_weather_forecast"),
    ("Prediction for Toronto weather tomorrow.", "get_weather_forecast"),
    ("Future weather in Moscow for the next 3 days.", "get_weather_forecast"),
    ("Expected weather in Oslo tomorrow.", "get_weather_forecast"),
    ("Is it going to be windy in Cape Town this weekend?", "get_weather_forecast"),
    ("Weather outlook for Seoul next month.", "get_weather_forecast"),
    ("Will it be hot in Dubai tomorrow?", "get_weather_forecast"),
    ("Forecast for Beijing tomorrow.", "get_weather_forecast"),
    # History (16)
    ("What was the weather like in London yesterday?", "get_weather_history"),
    ("Did it rain in Paris last Christmas?", "get_weather_history"),
    ("Temperature in Berlin on July 4th, 2023.", "get_weather_history"),
    ("How much snow fell in NYC last winter?", "get_weather_history"),
    ("Weather records for Tokyo in 1990.", "get_weather_history"),
    ("Was it sunny in Sydney on my birthday last year?", "get_weather_history"),
    ("History of weather in Madrid for August 2022.", "get_weather_history"),
    ("Past weather in Rome for June last year.", "get_weather_history"),
    ("What was the weather in Chicago on January 1st?", "get_weather_history"),
    ("Historical data for Seattle weather in 2010.", "get_weather_history"),
    ("Last week's weather in Toronto.", "get_weather_history"),
    ("How cold was it in Moscow in December 2020?", "get_weather_history"),
    ("Weather in Oslo yesterday afternoon.", "get_weather_history"),
    ("Cape Town weather history for last summer.", "get_weather_history"),
    ("Was it raining in Seoul three days ago?", "get_weather_history"),
    ("Past temperature in Dubai on Feb 1st.", "get_weather_history"),
]


def accuracy_bar(correct, total, width=20):
    """Returns a Rich Text object representing a visual accuracy bar.

    The bar's color depends on the percentage: green for high accuracy,
    yellow for moderate, and red for low.
    """
    pct = correct / total
    filled = round(pct * width)
    bar = "X" * filled + "." * (
        width - filled
    )  # X marks the progress, . marks the remaining
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def display_llm_exchange(query, response_text):
    """Renders a formatted view of the user query and model response to the terminal.

    Side effect: Prints multiple panels using the global console object.
    """
    messages = [{"role": "user", "content": query}]
    input_elements = []
    for msg in messages:
        role = msg["role"]
        content = (
            msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        )

        if role == "system":
            label_style = "dim"
            content_style = "dim"
        elif role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "assistant":
            label_style = "bold green"
            content_style = "green"
        elif role == "tool":
            label_style = "bold yellow"
            content_style = "yellow"
        else:
            label_style = "bold white"
            content_style = "white"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()  # Remove trailing rule

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    # align assistant text with the label length to keep a clean margin
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


def run_calibration(strategy_label, tools, color):
    """Runs all test queries against the model using a specific set of tools.

    Returns the count of correct tool selections and the total query count.
    Side effect: Prints real-time progress and timing data to the console.
    """
    console.print(
        f"[bold {color}]-- {strategy_label} Schema Calibration --------------------------------------[/bold {color}]"
    )
    console.print()

    model = genai.GenerativeModel(MODEL_NAME, tools=tools)
    correct = 0
    total = len(QUERIES)
    results = []

    for i, (query, expected) in enumerate(QUERIES):
        start_time = time.time()
        try:
            response = model.generate_content(query)
            elapsed = time.time() - start_time

            # look for the first function call in the model response parts
            tool_calls = response.candidates[0].content.parts
            selected_tool = None
            for part in tool_calls:
                if part.function_call:
                    selected_tool = part.function_call.name
                    break

            passed = selected_tool == expected
            if passed:
                correct += 1

            results.append((query, expected, selected_tool, passed))

            # show a visual sample for the first query only to verify rendering
            if i == 0:
                display_llm_exchange(query, f"Selected tool: {selected_tool}")

            # output a compact status dot to track progress across 50 runs
            dot = "[green]o[/green]" if passed else "[red]o[/red]"
            console.print(
                f"  Run #{i+1:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
                end="   ",
                highlight=False,
            )
            # break into a new line every five runs for readability
            if (i + 1) % 5 == 0:
                console.print()
        except Exception as e:
            console.print(f"\n[bold red]Error on query {i+1}:[/bold red] {str(e)}")
            results.append((query, expected, "ERROR", False))

    console.print("\n")
    return correct, total


def main():
    """Entry point to compare model performance between vague and specific tool schemas.

    Executes both 'Loose' and 'Tight' calibration suites and prints a summary
    table showing the accuracy delta.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Tool Schema Calibration[/bold yellow]\n"
            "[dim]Measuring the impact of description quality on LLM tool selection.[/dim]\n"
            "[dim]50 queries x 2 strategies (Loose vs Tight)[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # measure baseline with ambiguous tool descriptions
    loose_correct, total = run_calibration("Loose", LOOSE_TOOLS, "cyan")
    console.print(Rule("[bold]Intermediate Results[/bold]", style="white"))
    console.print(f"Loose Accuracy: ", end="")
    console.print(accuracy_bar(loose_correct, total))
    console.print()

    # measure performance with disambiguated descriptions
    tight_correct, _ = run_calibration("Tight", TIGHT_TOOLS, "magenta")

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Calibration Results", show_lines=True)
    table.add_column("Strategy", style="bold", min_width=24)
    table.add_column("Score", justify="center")
    table.add_column("Accuracy Bar", min_width=30)

    table.add_row(
        "Loose (Overlapping)",
        f"{loose_correct}/{total}",
        accuracy_bar(loose_correct, total),
    )
    table.add_row(
        "Tight (Disambiguated)",
        f"{tight_correct}/{total}",
        accuracy_bar(tight_correct, total),
    )

    # calculate how many more queries the 'Tight' strategy got right
    lift = tight_correct - loose_correct
    lift_str = (
        f"[green]+{lift}[/green]"
        if lift > 0
        else f"[red]{lift}[/red]" if lift < 0 else "[dim]+/-0[/dim]"
    )

    table.add_section()
    table.add_row("[bold]Accuracy Delta[/bold]", lift_str, "")

    console.print(table)
    console.print()

    # provide a final assessment based on the score difference
    if lift > 5:
        verdict = "[bold green]Significant Improvement![/bold green] Tightening schemas clearly reduces LLM confusion."
    elif lift > 0:
        verdict = "[bold yellow]Minor Improvement.[/bold yellow] The model is robust, but better schemas still help."
    else:
        verdict = "[bold cyan]No Change.[/bold cyan] The model was already accurate or the descriptions didn't clarify enough."

    console.print(f"VERDICT: {verdict}")
    console.print()


if __name__ == "__main__":
    main()
