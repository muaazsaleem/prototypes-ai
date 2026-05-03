import os
import time
import textwrap
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize the Rich console for professional terminal output
console = Console()

# Configuration
# The new SDK often prefers the slug without the "models/" prefix.
MODEL_ID = "gemini-2.5-flash"

# Migration Note: The new google-genai SDK uses genai.Client for all interactions.
# This replaces the previous global configuration pattern (genai.configure).
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# We define tools using the new SDK's types to maintain precise control over descriptions.
# This allows us to simulate "Loose" vs "Tight" schema calibration.

LOOSE_TOOLS = [
    # Migration Note: Tools are now defined using types.FunctionDeclaration and types.Schema.
    # This provides a more structured and type-safe way to define tool interfaces.
    types.FunctionDeclaration(
        name="get_weather_current",
        description="Get weather information for a location.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_weather_forecast",
        description="Get weather data for a city.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_weather_history",
        description="Fetch weather records for a specific area.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
    ),
]

TIGHT_TOOLS = [
    # Disambiguated descriptions help the model distinguish between similar tools.
    types.FunctionDeclaration(
        name="get_weather_current",
        description="Get CURRENT, REAL-TIME weather conditions for a specific location. Use only for queries about 'now', 'today', or current status.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_weather_forecast",
        description="Get FUTURE weather predictions and forecasts. Use only for queries about 'tomorrow', 'next week', 'upcoming', or future dates.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_weather_history",
        description="Fetch HISTORICAL weather records from the past. Use only for queries about yesterday, last year, or specific past dates.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING", description="The city name.")
            },
            required=["location"],
        ),
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
    """Generates a Rich Text accuracy bar with color-coded success levels.

    The color transitions from red (<50%) to yellow (>=50%) to green (>=80%).
    Returns a rich.text.Text object ready for console printing.
    """
    pct = correct / total
    filled = round(pct * width)
    # create a simple ASCII-style bar with background markers
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def display_llm_exchange(query, response_text):
    """Renders a visual representation of the LLM input and output.

    Uses Rich panels and rules to create a clear separation between the
    user's query and the model's generated response.
    """
    messages = [{"role": "user", "content": query}]
    input_elements = []
    for msg in messages:
        role = msg["role"]
        content = (
            msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        )

        # assign specific styles based on message roles
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
        input_elements.pop()  # remove the last rule for cleaner aesthetics

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
    """Evaluates the model's tool selection accuracy for a set of tools.

    Runs every query in QUERIES through the model and compares the selected
    tool against the expected one. Returns the number of correct hits and total count.
    """
    console.print(
        f"[bold {color}]-- {strategy_label} Schema Calibration --------------------------------------[/bold {color}]"
    )
    console.print()

    # Migration Note: GenerateContentConfig replaces the tool list in the generation call.
    # It allows for more complex configurations including system instructions and tool settings.
    tool_config = types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=tools)]
    )

    correct = 0
    total = len(QUERIES)
    results = []

    for i, (query, expected) in enumerate(QUERIES):
        start_time = time.time()
        try:
            # Migration Note: client.models.generate_content is the new entry point for generation.
            # This is significantly different from the previous model.generate_content() call.
            response = client.models.generate_content(
                model=MODEL_ID, contents=query, config=tool_config
            )
            elapsed = time.time() - start_time

            # Identify which tool the model selected by inspecting the response parts
            selected_tool = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    # Migration Note: Check for function_call on the part object directly.
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

            # output a compact status dot to track progress visually
            dot = "[green]o[/green]" if passed else "[red]o[/red]"
            console.print(
                f"  Run #{i+1:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
                end="   ",
                highlight=False,
            )
            # break into a new line every five runs for terminal readability
            if (i + 1) % 5 == 0:
                console.print()
        except Exception as e:
            console.print(f"\n[bold red]Error on query {i+1}:[/bold red] {str(e)}")
            results.append((query, expected, "ERROR", False))

    console.print("\n")
    return correct, total


def main():
    """Entry point to compare model performance across different schema strategies.

    Orchestrates the calibration runs and displays a summary table with the results.
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

    # run the baseline strategy with vague descriptions
    loose_correct, total = run_calibration("Loose", LOOSE_TOOLS, "cyan")
    console.print(Rule("[bold]Intermediate Results[/bold]", style="white"))
    console.print(f"Loose Accuracy: ", end="")
    console.print(accuracy_bar(loose_correct, total))
    console.print()

    # run the optimized strategy with disambiguated descriptions
    tight_correct, _ = run_calibration("Tight", TIGHT_TOOLS, "magenta")

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()

    # build the final comparison table
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

    # calculate the performance lift between strategies
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

    # determine the final verdict based on the delta
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
