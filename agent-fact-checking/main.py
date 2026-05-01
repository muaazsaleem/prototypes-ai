import json
import sys
import textwrap

from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.text import Text

from config import GEMINI_API_KEY, SAMPLE_PASSAGE, VOTING_ROUNDS
from decomposer import DECOMPOSE_PROMPT, decompose_passage
from evidence import EVIDENCE_PROMPT, gather_evidence
from reporter import build_report, display_report
from voter import VOTE_PROMPT, vote_on_claim

console = Console()


def display_llm_communication(prompt: str, response_data: dict, title: str) -> None:
    """
    Styles and prints the LLM input and response using the rich library.

    Uses bright_black panels for containers and specific persona labels for
    clarity. The input is wrapped to 82 characters, and the response is
    shown as a structured assistant message.
    """
    # Model Input Block
    input_elements = []
    # In this pipeline, the role is typically a user prompt
    role = "user"
    label_style = "bold blue"
    content_style = "blue"

    indent = " " * (len(role) + 2)
    wrapped_prompt = textwrap.fill(prompt, width=82, subsequent_indent=indent)

    input_elements.append(
        Text.assemble(
            (f"{role.upper()}: ", label_style), (wrapped_prompt, content_style)
        )
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

    # Model Output Block
    # Convert response data to a clean JSON string for verbatim-like display
    response_text = json.dumps(response_data, indent=2)
    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
    )

    console.print(
        Panel(
            response_content,
            title=f"[bold bright_black]{title} Response[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def run_fact_check(passage: str) -> None:
    """
    Orchestrates the full fact-checking pipeline for a given passage.

    Decomposes the input into atomic claims, gathers evidence for each, runs
    self-consistency voting, and generates a final report. Missing API keys
    result in an immediate exit.
    """
    if not GEMINI_API_KEY:
        # Halt execution if the required API key is not found in the environment
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        raise SystemExit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Display the opening header panel with project details
    console.print(
        Panel.fit(
            "[bold yellow]Fact-Checking Agent[/bold yellow]\n"
            "[dim]Decomposes a passage into atomic claims and verifies each one.[/dim]\n"
            f"[dim]{VOTING_ROUNDS} voting rounds per claim · Gemini 2.5 Flash[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Step 1: Decompose the passage into atomic claims
    console.print(Rule("[bold]Step 1 — Decompose[/bold]", style="white"))
    console.print()

    # To follow terminal-output-style, we display the communication for the decomposition step
    # We reconstruct the prompt using the imported template
    decompose_prompt = DECOMPOSE_PROMPT.format(passage=passage)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True
    ) as progress:
        progress.add_task("Splitting passage into atomic claims...", total=None)
        claims = decompose_passage(client, passage)

    # Display the communication after the step completes to avoid progress bar interference
    display_llm_communication(
        decompose_prompt, {"claims": [c.text for c in claims]}, "Decomposition"
    )

    console.print(
        f"  [green]✓[/green] Found [bold]{len(claims)}[/bold] atomic claims to verify."
    )
    console.print()

    # Step 2: Gather supporting and contradicting evidence for each claim
    console.print(Rule("[bold]Step 2 — Gather Evidence[/bold]", style="white"))
    console.print()
    evidences = []
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True
    ) as progress:
        task = progress.add_task("", total=len(claims))
        for claim in claims:
            # Update progress description for the current claim being processed
            progress.update(
                task,
                description=f"[dim]Evidence for claim {claim.index}/{len(claims)}...[/dim]",
            )
            ev = gather_evidence(client, claim.text)
            evidences.append(ev)

            # For brevity in the terminal, we show the first claim's communication as a sample
            if claim.index == 1:
                evidence_prompt = EVIDENCE_PROMPT.format(claim=claim.text)
                # We'll display it after the progress bar for this claim advances
                # but since progress is transient, it's cleaner to show it once at the end
                # or just show the first one here.

            progress.advance(task)

    # Show first claim evidence communication as a sample of the underlying process
    if evidences:
        first_ev = evidences[0]
        sample_prompt = EVIDENCE_PROMPT.format(claim=first_ev.claim)
        display_llm_communication(
            sample_prompt,
            {
                "supporting": first_ev.supporting,
                "contradicting": first_ev.contradicting,
            },
            "Evidence Gathering (Sample)",
        )

    console.print(
        f"  [green]✓[/green] Evidence gathered for [bold]{len(claims)}[/bold] claims."
    )
    console.print()

    # Step 3: Self-consistency voting — run VOTING_ROUNDS independent LLM calls per claim
    console.print(Rule("[bold]Step 3 — Self-Consistency Voting[/bold]", style="white"))
    console.print()
    results = []
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True
    ) as progress:
        task = progress.add_task("", total=len(evidences))
        for i, ev in enumerate(evidences, start=1):
            # Show voting progress with the number of rounds specified in config
            progress.update(
                task,
                description=f"[dim]Voting on claim {i}/{len(evidences)} ({VOTING_ROUNDS} rounds)...[/dim]",
            )
            vote_result = vote_on_claim(client, ev)
            results.append(vote_result)
            progress.advance(task)

    # Show first claim voting communication as a sample
    if results:
        first_res = results[0]
        # For the sample, we reconstruct what a single vote call would look like
        sample_vote_prompt = VOTE_PROMPT.format(
            claim=first_res.claim,
            supporting=(
                "\n".join(f"- {e}" for e in evidences[0].supporting)
                if evidences[0].supporting
                else "- None found"
            ),
            contradicting=(
                "\n".join(f"- {e}" for e in evidences[0].contradicting)
                if evidences[0].contradicting
                else "- None found"
            ),
        )
        display_llm_communication(
            sample_vote_prompt,
            {"verdict": first_res.final_verdict, "reasoning": first_res.reasoning},
            "Voting (Sample)",
        )

    console.print(
        f"  [green]✓[/green] Voting complete for [bold]{len(claims)}[/bold] claims."
    )
    console.print()

    # Step 4: Build and display the final report
    report = build_report(passage, evidences, results)
    display_report(report, evidences)


if __name__ == "__main__":
    # Use provided command line argument or fall back to sample passage
    passage = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_PASSAGE
    run_fact_check(passage)
