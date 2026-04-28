import os
import textwrap
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize the rich Console
console = Console()

# Initialize the Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

# Use gemini-2.5-flash
MODEL = "gemini-2.5-flash"

# --------------------------------------------------------------------------- #
# Tool — simulated weather service
# --------------------------------------------------------------------------- #

TOOL_CALL_COUNT = 0

def get_weather(city: str) -> dict:
    """Returns the current weather for a city or a simulated 503 error."""
    global TOOL_CALL_COUNT
    TOOL_CALL_COUNT += 1

    if TOOL_CALL_COUNT == 1:
        return {
            "city": city, 
            "temperature_c": 28, 
            "condition": "Sunny", 
            "humidity_pct": 45
        }
    else:
        return {
            "error": "SERVICE_UNAVAILABLE",
            "http_status": 503,
            "detail": f"Upstream weather API timed out for '{city}'",
        }

# --------------------------------------------------------------------------- #
# UI Helpers — following terminal-output-style skill
# --------------------------------------------------------------------------- #

def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Standard accuracy bar from terminal-output-style skill."""
    pct = correct / total
    filled = round(pct * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)

def print_contents(contents: list):
    """Prints the conversation history following skill conventions."""
    console.print(Rule("[bold]Current Conversation History[/bold]", style="white", align="left"))
    for content in contents:
        role = content.role.upper()
        # Strategy A (User) = Cyan, Strategy B (Model) = Magenta (per skill semantics)
        color = "cyan" if role == "USER" else "magenta"
        
        for part in content.parts:
            if part.text:
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = "[dim]Message:[/dim]"
                wrapped = textwrap.fill(part.text.strip(), width=88, subsequent_indent="         ")
                console.print(f"  {prefix} {wrapped}")
            elif part.function_call:
                fc = part.function_call
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = "[dim]Action:[/dim]"
                console.print(f"  {prefix} [bold yellow]CALLING TOOL:[/bold yellow] {fc.name}({fc.args})")
            elif part.function_response:
                fr = part.function_response
                is_err = "error" in fr.response
                res_color = "red" if is_err else "green"
                console.print(f"\n[bold {color}]> {role}[/bold {color}]")
                prefix = f"[dim]Result ([yellow]{fr.name}[/yellow]):[/dim]"
                console.print(f"  {prefix} [{res_color}]{fr.response}[/{res_color}]")
    console.print()

# --------------------------------------------------------------------------- #
# Agentic loop
# --------------------------------------------------------------------------- #

def run_agent(system_prompt: str, user_message: str, strategy_label: str, strategy_color: str) -> dict:
    """Orchestrates the conversation with professional terminal styling."""
    global TOOL_CALL_COUNT
    TOOL_CALL_COUNT = 0

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[get_weather],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]

    tool_calls_total = 0
    tool_successes = 0
    tool_errors = 0
    rounds = 0
    final_text = ""

    while True:
        rounds += 1
        console.print(Rule(f"[bold white]ROUND {rounds}[/bold white]", style="blue"))
        
        print_contents(contents)
        
        print("asking llm...")
        response = client.models.generate_content(model=MODEL, contents=contents, config=config)
        candidate = response.candidates[0].content

        fn_calls = [p for p in candidate.parts if p.function_call]
        text_parts = [p.text for p in candidate.parts if p.text and p.text.strip()]

        if not fn_calls:
            final_text = " ".join(text_parts)
            console.print(f"\n[bold {strategy_color}]-- Final Response --------------------------------------[/bold {strategy_color}]")
            wrapped = textwrap.fill(final_text, width=88, subsequent_indent="  ")
            console.print(f"  {wrapped}\n")
            break

        contents.append(types.Content(role="model", parts=candidate.parts))

        result_parts = []
        for part in fn_calls:
            # Inspection of raw model output as requested
            console.print("[dim]Raw tool call part from model:[/dim]")
            console.print(part.function_call)
            
            fc = part.function_call
            console.print(f"[dim]Executing tool [yellow]{fc.name}[/yellow] with [yellow]{fc.args}[/yellow]...[/dim]")
            
            tool_calls_total += 1
            result = get_weather(**dict(fc.args))

            if "error" in result:
                tool_errors += 1
                console.print(f"  └── [bold red][FAILURE][/bold red] {result['error']}")
            else:
                tool_successes += 1
                console.print(f"  └── [bold green][SUCCESS][/bold green] Weather retrieved")

            result_parts.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )

        contents.append(types.Content(role="user", parts=result_parts))

    return {
        "tool_calls": tool_calls_total,
        "tool_successes": tool_successes,
        "tool_errors": tool_errors,
        "rounds": rounds,
        "response": final_text,
    }

# --------------------------------------------------------------------------- #
# Main execution
# --------------------------------------------------------------------------- #

def main():
    # Opening header - following skill exactly
    console.print(
        Panel.fit(
            "[bold yellow]Tool Call Error Injection & Handling[/bold yellow]\n"
            "[dim]Demonstrating model transparency when upstream APIs fail.[/dim]\n"
            "[dim]2 scenarios × 1 tool × 2 cities[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    QUESTION = "What is the current weather in Tokyo and London?"

    # Scenario A
    console.print("[bold cyan]-- Scenario A: No Error Guidance --------------------------[/bold cyan]")
    a = run_agent("You are a helpful weather assistant.", QUESTION, "Scenario A", "cyan")

    # Scenario B
    console.print("[bold magenta]-- Scenario B: With Explicit Guidance ---------------------[/bold magenta]")
    b_prompt = (
        "You are a helpful weather assistant. "
        "If a tool returns an error field, you MUST report it explicitly: "
        "state code and details. Do not guess."
    )
    b = run_agent(b_prompt, QUESTION, "Scenario B", "magenta")

    # Overall Summary
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))

    table = Table(title="Injection Test Results", show_lines=True)
    table.add_column("Scenario", min_width=25)
    table.add_column("Rounds", justify="center")
    table.add_column("Success Rate", justify="right")
    table.add_column("Reported 503?", justify="center")

    def reported_503(text):
        found = '503' in text or 'SERVICE_UNAVAILABLE' in text
        return "[bold green]YES[/bold green]" if found else "[bold red]NO[/bold red]"

    table.add_row(
        "[cyan]Scenario A[/cyan]",
        str(a['rounds']),
        accuracy_bar(a['tool_successes'], a['tool_calls']),
        reported_503(a['response'])
    )
    table.add_row(
        "[magenta]Scenario B[/magenta]",
        str(b['rounds']),
        accuracy_bar(b['tool_successes'], b['tool_calls']),
        reported_503(b['response'])
    )

    console.print(table)
    console.print()

if __name__ == "__main__":
    main()
