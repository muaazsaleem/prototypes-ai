import os
import json
import time
import textwrap
from datetime import datetime
from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"  # High-speed model for rapid indexing
INDEX_FILE = "project_index.json"

# Initialize Rich Console for styled terminal output
console = Console()


class GeminiAgent:
    """Wrapper for Gemini API to handle file summarization, token counting, and queries."""

    def __init__(self, api_key, model_name):
        """Initializes the Gemini model with the provided API key."""
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def count_tokens(self, text):
        """Calculates the exact token count for a given string.

        Falls back to a rough character-based estimate if the API call fails.
        """
        try:
            response = self.client.models.count_tokens(
                model=self.model_name,
                contents=text,
            )
            return response.total_tokens
        except Exception:
            return len(text) // 4

    def summarize_file(self, file_path, content):
        """Sends file content to Gemini to generate a summary and extract symbols.

        Returns a dictionary with 'summary' and 'symbols' keys.
        """
        prompt = f"""
        Summarize the following file content and identify key symbols (functions, classes, variables).
        File Path: {file_path}
        
        Content:
        {content}
        
        Return the result in JSON format:
        {{
            "summary": "Short summary here",
            "symbols": ["symbol1", "symbol2"]
        }}
        """

        self._display_input([{"role": "user", "content": prompt}])

        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            response_text = response.text
            self._display_output(response_text)
        except Exception as e:
            console.print(f"[bold red]Error querying the model:[/bold red] {e}")
            return {"summary": "Error calling API", "symbols": [], "error": str(e)}

        try:
            # Strip markdown code blocks if present in the model response
            json_str = response_text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith("```"):
                json_str = json_str[3:-3].strip()
            return json.loads(json_str)
        except Exception as e:
            return {"summary": "Error parsing summary", "symbols": [], "error": str(e)}

    def answer_query(self, query, index_data):
        """Answers a user query using only the structured index data as context.

        This demonstrates how the agent solves problems without reading raw code files.
        """
        context_payload = json.dumps(index_data, indent=2)
        prompt = f"""
        You are a helpful coding assistant. Use ONLY the following project index to answer the user's query.
        Do not assume the existence of any files or functions not listed here.
        
        Project Index:
        {context_payload}
        
        User Query:
        {query}
        """

        self._display_input([{"role": "user", "content": prompt}])
        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            self._display_output(response.text)
        except Exception as e:
            console.print(f"[bold red]Error querying the model:[/bold red] {e}")

    def _display_input(self, messages):
        """Styles and prints the model input block to the console."""
        input_elements = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            label_style = "bold blue" if role == "user" else "dim"
            content_style = "blue" if role == "user" else "dim"

            indent = " " * (len(role) + 2)
            wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
            input_elements.append(
                Text.assemble(
                    (f"{role.upper()}: ", label_style), (wrapped, content_style)
                )
            )
            input_elements.append(Rule(style="bright_black"))

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

    def _display_output(self, response_text):
        """Styles and prints the model response block to the console."""
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


class ProjectIndex:
    """Manages a persistent JSON index of project files and their metadata."""

    def __init__(self, index_file):
        """Loads the existing index from disk or initializes an empty one."""
        self.index_file = index_file
        self.index = self._load_index()

    def _load_index(self):
        """Reads the index JSON file if it exists."""
        if os.path.exists(self.index_file):
            with open(self.index_file, "r") as f:
                return json.load(f)
        return {}

    def _save_index(self):
        """Writes the current in-memory index to the JSON file."""
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=4)

    def get_file_info(self, file_path):
        """Checks if a file is in the index and if it is stale relative to disk.

        Returns 'stale' if file has changed since last index, the info dict if fresh,
        or None if the file is not tracked.
        """
        if not os.path.exists(file_path):
            return None

        mtime = os.path.getmtime(file_path)
        last_read = self.index.get(file_path, {}).get("last_read", 0)

        if mtime > last_read:
            return "stale"
        return self.index.get(file_path)

    def update_file(self, file_path, summary, symbols):
        """Updates the index entry for a file with new summary and symbol data."""
        self.index[file_path] = {
            "summary": summary,
            "symbols": symbols,
            "last_read": time.time(),
            "timestamp": datetime.now().isoformat(),
        }
        self._save_index()


def run_prototype():
    """Main execution loop demonstrating lazy indexing, token savings, and context queries."""
    console.print(
        Panel.fit(
            "[bold yellow]Structured Project Index Agent[/bold yellow]\n"
            "[dim]Demonstrating lazy indexing, staleness checks, and token optimization with Gemini 2.5 Flash.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    agent = GeminiAgent(GEMINI_API_KEY, MODEL_NAME)
    project_index = ProjectIndex(INDEX_FILE)

    files_to_index = [
        f
        for f in os.listdir(".")
        if f.endswith(".py") and f != "project_indexer_agent.py"
    ]

    console.print(Rule("[bold]Phase 1: Lazy Indexing[/bold]", style="white"))
    console.print()

    stats = {"total": len(files_to_index), "stale": 0, "fresh": 0, "errors": 0}
    raw_code_content = ""

    for file_path in files_to_index:
        info = project_index.get_file_info(file_path)

        # Accumulate raw code for token comparison later
        with open(file_path, "r") as f:
            file_content = f.read()
            raw_code_content += f"File: {file_path}\n{file_content}\n\n"

        if info == "stale" or info is None:
            stats["stale"] += 1
            console.print(
                f"[yellow]![/yellow] Indexing stale/new file: [bold]{file_path}[/bold]"
            )
            try:
                result = agent.summarize_file(file_path, file_content)
                if "error" in result:
                    stats["errors"] += 1
                else:
                    project_index.update_file(
                        file_path, result["summary"], result["symbols"]
                    )
            except Exception as e:
                console.print(f"[red]Error indexing {file_path}: {e}[/red]")
                stats["errors"] += 1
        else:
            stats["fresh"] += 1
            console.print(
                f"[green]✓[/green] Using cached index for: [bold]{file_path}[/bold]"
            )

    console.print()

    console.print(
        Rule("[bold]Phase 2: Token Optimization Analysis[/bold]", style="white")
    )
    console.print()

    # Calculate token sizes
    raw_tokens = agent.count_tokens(raw_code_content)
    index_payload = json.dumps(project_index.index, indent=2)
    index_tokens = agent.count_tokens(index_payload)
    saved_tokens = raw_tokens - index_tokens

    # Render token savings comparison
    token_table = Table(show_edge=False, show_lines=False, pad_edge=False, expand=True)
    token_table.add_column("Strategy", style="bold")
    token_table.add_column("Tokens", justify="right")

    token_table.add_row(
        "Naïve Approach (Sending Raw Files)", f"[red]{raw_tokens:,}[/red]"
    )
    token_table.add_row(
        "Agentic Approach (Sending Index)", f"[green]{index_tokens:,}[/green]"
    )
    token_table.add_row(
        "Tokens Saved per Query", f"[bold cyan]{saved_tokens:,}[/bold cyan]"
    )

    console.print(
        Panel(
            token_table,
            title="[bold dim]Context Payload Comparison[/bold dim]",
            border_style="dim",
        )
    )
    console.print()

    console.print(Rule("[bold]Phase 3: Querying the Project[/bold]", style="white"))
    console.print()

    # Simulate a user query using only the lightweight index
    query = "I need to parse a CSV file and then calculate the sum of a specific column. Which files and functions should I use from this project?"
    agent.answer_query(query, project_index.index)

    console.print()
    console.print(
        Rule("[bold yellow]Final Status and Stats[/bold yellow]", style="yellow")
    )
    console.print()

    table = Table(title="Indexing Results", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="center")

    table.add_row("Total Files Tracked", str(stats["total"]))
    table.add_row("Files Indexed (Stale)", f"[yellow]{stats['stale']}[/yellow]")
    table.add_row("Files Reused (Fresh)", f"[green]{stats['fresh']}[/green]")
    table.add_row("Errors encountered", f"[red]{stats['errors']}[/red]")

    console.print(table)
    console.print()

    if stats["errors"] == 0:
        verdict = "[bold green]PASS[/bold green]: Agent successfully indexed files and answered queries using optimized context."
    else:
        verdict = "[bold red]FAIL[/bold red]: Some files failed to index."

    console.print(f"Verdict: {verdict}")
    console.print()


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY not found in environment."
        )
    else:
        run_prototype()
