import asyncio
import textwrap
from typing import Any, Callable

from opentelemetry import trace
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from cache import PromptCacheManager
from google import genai
from models import Workflow, WorkflowNode, NodeType
from nodes import run_node, WORKFLOW_SYSTEM_PROMPT


def _build_execution_waves(workflow: Workflow) -> list[list[WorkflowNode]]:
    """Topologically sorts workflow nodes into parallel execution waves.

    Groups nodes that can be executed concurrently based on their dependency
    structure. Ensures that no node is scheduled before its upstream
    requirements are met. Raises ValueError if a circular dependency is detected.
    """
    completed: set[str] = set()
    remaining = list(workflow.nodes)
    waves: list[list[WorkflowNode]] = []

    while remaining:
        # identify nodes whose dependencies are all satisfied
        ready = [
            node
            for node in remaining
            if all(dep in completed for dep in node.depends_on)
        ]
        if not ready:
            stuck = [n.id for n in remaining]
            raise ValueError(
                f"Cycle detected — these nodes cannot be scheduled: {stuck}"
            )

        waves.append(ready)
        for node in ready:
            completed.add(node.id)
        # remove scheduled nodes from the pool
        remaining = [n for n in remaining if n.id not in completed]

    return waves


async def _run_node_buffered(
    node: WorkflowNode,
    results: dict[str, str],
    tracer: trace.Tracer,
    client: genai.Client,
    cache_manager: PromptCacheManager,
) -> tuple[str, str, str | None]:
    """Executes a single node and buffers its output to prevent interleaving.

    Collects all streamed chunks from the node runner and returns the full
    output as a single string. For LLM nodes, also returns the raw user message.
    """
    inputs = {dep: results[dep] for dep in node.depends_on}
    chunks: list[str] = []
    user_message = None

    # For LLM nodes, we reconstruct the user message for display purposes.
    if node.type not in (NodeType.FETCH, NodeType.EMAIL, NodeType.TEMPORAL_HITL):
        input_block = (
            "\n\n".join(
                f"### Input from [{dep}]\n{text}" for dep, text in inputs.items()
            )
            if inputs
            else "(no upstream input)"
        )
        user_message = f"""Node id:     {node.id}
Operation:   {node.type.value}
Description: {node.description}
Params:      {node.params}

--- INPUT DATA ---
{input_block}
--- END INPUT ---

Execute the operation described above on the input data."""

    # wrap node execution in a trace span for observability
    with tracer.start_as_current_span(f"node.{node.id}") as span:
        span.set_attribute("node.type", node.type.value)
        span.set_attribute("node.description", node.description)
        span.set_attribute("node.depends_on", str(node.depends_on))

        async for chunk in run_node(node, inputs, client, cache_manager):
            chunks.append(chunk)

    return node.id, "".join(chunks), user_message


def print_llm_io(
    print_fn: Callable[..., None],
    node_id: str,
    user_message: str,
    response_text: str,
    system_prompt: str = WORKFLOW_SYSTEM_PROMPT,
) -> None:
    """Prints the LLM input and response using styled rich panels."""

    # 1. Model Input Block
    input_elements = []
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            label_style = "dim"
            content_style = "dim"
        elif role == "user":
            label_style = "bold blue"
            content_style = "blue"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()

    print_fn(
        Panel(
            Group(*input_elements),
            title=f"[bold bright_black]Model Input ({node_id})[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    # 2. Model Output Block
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
    )

    print_fn(
        Panel(
            response_content,
            title=f"[bold bright_black]Model Response ({node_id})[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    print_fn()


async def execute_workflow(
    workflow: Workflow,
    tracer: trace.Tracer,
    client: genai.Client,
    cache_manager: PromptCacheManager,
    print_fn: Callable[..., None],
) -> dict[str, Any]:
    """Executes the workflow DAG wave by wave and prints results.

    Orchestrates the full execution lifecycle: sorting nodes, running waves
    concurrently using asyncio.gather, and printing per-node results sequentially
    once each wave completes.
    """
    results: dict[str, str] = {}
    waves = _build_execution_waves(workflow)

    # root span for the entire workflow execution
    with tracer.start_as_current_span("workflow.execute") as root_span:
        root_span.set_attribute("workflow.name", workflow.name)
        root_span.set_attribute("workflow.node_count", len(workflow.nodes))
        root_span.set_attribute("workflow.wave_count", len(waves))

        for wave_idx, wave in enumerate(waves, start=1):
            node_ids = [n.id for n in wave]

            if len(wave) > 1:
                print_fn(
                    f"\n[bold yellow]⚡ Wave {wave_idx} — "
                    f"running {len(wave)} nodes in parallel: {node_ids}[/bold yellow]"
                )
            else:
                print_fn(
                    f"\n[bold yellow]▸ Wave {wave_idx} — {node_ids[0]}[/bold yellow]"
                )

            # fire all nodes in the current wave simultaneously
            tasks = [
                _run_node_buffered(node, results, tracer, client, cache_manager)
                for node in wave
            ]
            outputs = await asyncio.gather(*tasks)

            # print results sequentially to maintain readability
            for node_id, output, user_message in outputs:
                node = next(n for n in wave if n.id == node_id)

                if user_message:
                    # use the professional LLM I/O styling
                    print_llm_io(
                        print_fn,
                        node_id,
                        user_message,
                        output,
                    )
                else:
                    # standard output for non-LLM nodes
                    print_fn(
                        f"\n[bold green]✔ {node_id}[/bold green] "
                        f"[dim]({node.type.value})[/dim]\n"
                    )
                    print_fn(output)

                results[node_id] = output

    return results
