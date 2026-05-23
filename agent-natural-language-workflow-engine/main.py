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

# A more complex workflow demonstrating Human-in-the-Loop (HITL) execution using Temporal,
# along with parallel execution and external MCP calls.
COMPLEX_WORKFLOW = (
    "In parallel, use the Hacker News MCP to fetch the top 5 stories about 'AI Agents' "
    "and use the GitHub MCP to fetch trending repositories related to 'Agents'. "
    "Summarise all the fetched data into a single Markdown draft report. "
    "Next, trigger a Human-in-the-Loop (HITL) approval step via Temporal to have a human review the draft. "
    "Wait for the human approval to complete. "
    "Finally, once approved, use the Slack MCP to publish the final report to the #engineering channel."
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


async def run(workflow_description: str, use_temporal: bool = False) -> None:
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
    if use_temporal:
        console.print(Rule("[bold magenta]Executing via Temporal[/bold magenta]"))
        console.print("[yellow]Note: This requires a running Temporal server and worker.[/yellow]")
        console.print("[dim]Connecting to Temporal...[/dim]")
        
        try:
            from temporalio.client import Client as TemporalClient
            from temporal_executor import NaturalLanguageWorkflow
            
            # Connect to local Temporal server
            temporal_client = await TemporalClient.connect("localhost:7233")
            
            # Start the workflow
            handle = await temporal_client.start_workflow(
                NaturalLanguageWorkflow.run,
                workflow.model_dump(),
                id=f"workflow-{workflow.name.replace(' ', '-').lower()}",
                task_queue="nl-workflow-queue",
            )
            
            console.print(f"[bold green]✔ Temporal Workflow Started![/bold green] ID: {handle.id}")
            console.print("[dim]Waiting for result...[/dim]")
            
            results = await handle.result()
            
            console.print(Rule("[bold cyan]Temporal Results[/bold cyan]"))
            for node_id, output in results.items():
                console.print(f"\n[bold green]✔ {node_id}[/bold green]")
                console.print(output)
                
        except Exception as e:
            console.print(f"[bold red]Temporal Execution Failed:[/bold red] {e}")
            console.print("[dim]Ensure Temporal is running: `temporal server start-dev`[/dim]")
            return
    else:
        console.print(Rule("[bold cyan]Executing Locally[/bold cyan]"))

        results = await execute_workflow(
            workflow,
            tracer,
            client,
            cache_manager,
            # pass the rich console's print method for styled executor output
            print_fn=console.print,
        )

    console.print(Rule("[bold cyan]Done[/bold cyan]"))
    if not use_temporal:
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
        "--example",
        choices=["1", "2"],
        help="Run a built-in example workflow (1=default, 2=complex HITL).",
    )
    parser.add_argument(
        "--temporal",
        action="store_true",
        help="Execute the workflow using Temporal instead of the local async executor.",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        help="Plain-English description of the workflow to execute.",
    )
    args = parser.parse_args()

    # Determine which workflow to run
    workflow_to_run = DEFAULT_WORKFLOW
    if args.example == "1":
        workflow_to_run = DEFAULT_WORKFLOW
    elif args.example == "2":
        workflow_to_run = COMPLEX_WORKFLOW
    elif args.workflow:
        workflow_to_run = args.workflow

    # start the event loop
    asyncio.run(run(workflow_to_run, use_temporal=args.temporal))


if __name__ == "__main__":
    main()
