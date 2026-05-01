import argparse
import asyncio
import os
import sys

from google import genai
from rich.console import Console
from rich.rule import Rule

from cache import PromptCacheManager
from executor import execute_workflow, print_llm_io
from parser import parse_workflow, PARSER_SYSTEM_PROMPT
from tracing import setup_tracing

# Change this env var to point at a different Gemini model without editing code.
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# A demo workflow that showcases parallel execution (fetch_hn and fetch_github
# run at the same time, then summarize in parallel, then aggregate + translate).
DEFAULT_WORKFLOW = (
    "Fetch the top 10 Hacker News posts and the top 5 trending GitHub repositories. "
    "Summarise the Hacker News posts. Summarise the GitHub repos. "
    "Combine both summaries into a unified tech digest. "
    "Translate the digest to Spanish."
)

console = Console()


def _print_dag(workflow) -> None:
    """Pretty-prints the parsed workflow DAG to the console for verification.

    Iterates through the nodes in the workflow and displays their IDs, types,
    and dependency relationships using Rich formatting.
    """
    console.print(f"\n[bold cyan]Workflow:[/bold cyan] {workflow.name}")
    console.print(f"[dim]{workflow.description}[/dim]\n")
    for node in workflow.nodes:
        # format dependency labels for readability
        deps = (
            f"  ← depends on [{', '.join(node.depends_on)}]"
            if node.depends_on
            else "  ← (no dependencies, runs immediately)"
        )
        console.print(f"  [bold]{node.id}[/bold] [dim]({node.type.value})[/dim]{deps}")


async def run(workflow_description: str) -> None:
    """Orchestrates the full lifecycle of a natural language workflow.

    Parses the English description into a DAG, sets up tracing and caching,
    and then executes the nodes. Requires GEMINI_API_KEY to be set.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY is not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    tracer = setup_tracing()
    cache_manager = PromptCacheManager(client, MODEL)

    # ── Step 1: Parse natural language → DAG ────────────────────────────────
    console.print(Rule("[bold cyan]Natural Language Workflow Engine[/bold cyan]"))
    console.print(f"\n[bold]Input:[/bold]\n{workflow_description}\n")
    console.print("[dim]Parsing workflow into DAG …[/dim]")

    workflow, raw_response = parse_workflow(workflow_description, client)

    # Use styled LLM I/O for the parsing step
    print_llm_io(
        console.print,
        "workflow_parser",
        f"Parse this workflow into a DAG:\n\n{workflow_description}",
        raw_response,
        system_prompt=PARSER_SYSTEM_PROMPT,
    )

    _print_dag(workflow)

    # ── Step 2: Execute the DAG ──────────────────────────────────────────────
    console.print(Rule("[bold cyan]Executing[/bold cyan]"))

    results = await execute_workflow(
        workflow,
        tracer,
        client,
        cache_manager,
        # pass the rich console's print method for styled executor output
        print_fn=console.print,
    )

    console.print(Rule("[bold cyan]Done[/bold cyan]"))
    console.print(
        f"[dim]Completed {len(results)} nodes. "
        "OpenTelemetry spans printed above (look for the JSON blocks).[/dim]"
    )


def main() -> None:
    """CLI entry point: parses arguments and starts the async execution loop."""
    parser = argparse.ArgumentParser(
        description="Run a natural-language workflow through the engine."
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        default=DEFAULT_WORKFLOW,
        help="Plain-English description of the workflow to execute.",
    )
    args = parser.parse_args()
    # start the event loop
    asyncio.run(run(args.workflow))


if __name__ == "__main__":
    main()
