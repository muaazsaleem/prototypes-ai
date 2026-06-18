import os
import textwrap
import warnings

# Suppress deprecation warnings before imports to keep output clean
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from ddgs import DDGS
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

console = Console()


def search(query):
    """Executes a real web search using DuckDuckGo and returns formatted text snippets.

    Performs a live network request. Returns a concatenated string of search result summaries
    or a fallback error message if the search fails.
    """
    # Clean query of surrounding quotes and whitespace
    query = query.strip("'\" ").lower()

    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "Search result: No information found."

        # Combine the body snippets into a single context string
        snippets = [f"- {res['body']}" for res in results]
        return "\n".join(snippets)
    except Exception as e:
        return f"Search failed: {str(e)}"


def print_llm_io(messages, response_text):
    """Displays formatted LLM interaction logs in the terminal using Rich panels.

    Iterates over previous messages to build an input panel, then prints the immediate
    response in a separate panel. Writes directly to standard output via the global console.
    """
    input_elements = []
    for msg in messages:
        # Map Gemini's 'model' role to 'assistant' to match terminal style guidelines
        role = "assistant" if msg.role == "model" else msg.role
        content = msg.parts[0].text

        if role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "assistant":
            label_style = "bold green"
            content_style = "green"
        else:
            label_style = "bold yellow"
            content_style = "yellow"

        # Indent subsequent lines of wrapped text to align with the role label
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    # Remove trailing rule from history panel
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

    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    console.print(
        Panel(
            Text.assemble(("ASSISTANT: ", "bold green"), (wrapped_response, "italic")),
            title="[bold bright_black]Model Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def run_agent(question):
    """Executes a multi-turn reasoning loop using a LLM to decide when to search or answer.

    Mutates the chat session by sending messages. Reads GEMINI_API_KEY from the environment.
    Returns the final answer string or a failure message if the 3-turn limit is reached
    without a conclusion.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat()

    # System-style instruction injected as the first user prompt
    prompt = f"You are a strict ReAct agent. Reason and act. Question: {question}"

    for _ in range(5):
        response = chat.send_message(prompt)

        # Exclude the current response from history to print it separately
        print_llm_io(chat.history[:-1], response.text)

        if response.text.startswith("ANSWER"):
            return response.text[7:].strip()

        # Parse query from SEARCH 'query' format and prepare next turn prompt
        query = response.text[7:].strip("'\" ")
        prompt = f"Search result for '{query}': {search(query)}"

    return "Failed to reach a conclusion."


if __name__ == "__main__":
    console.print(
        Panel.fit(
            "[bold yellow]Minimal Search Agent Prototype[/bold yellow]\n"
            "[dim]A 20-line core loop demonstrating the Search-Read-Decide pattern.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    question = "What is the population of the city where the author of 'The Three-Body Problem' was born?"
    console.print(
        f"[bold cyan]-- Question --------------------------------------[/bold cyan]"
    )

    console.print(f"  {question}\n")

    result = run_agent(question)

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()
    console.print(f"  [bold]Verdict:[/bold] [green]{result}[/green]\n")
