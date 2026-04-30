import json
import logging
import os
import textwrap
import time

from flask import Flask, Response, render_template, request, stream_with_context
from google import genai
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Suppress Flask's default request logs so only our rich output shows
logging.getLogger("werkzeug").setLevel(logging.ERROR)

console = Console()

app = Flask(__name__)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash-preview-04-17"


# ---------------------------------------------------------------------------
# Terminal display helpers (rich-styled)
# ---------------------------------------------------------------------------


def print_startup_header():
    """Print the opening banner when the Flask server starts."""
    console.print(
        Panel.fit(
            "[bold yellow]Token Streaming Demo[/bold yellow]\n"
            "[dim]Streaming vs Non-Streaming perceived latency[/dim]\n"
            f"[dim]Model: {MODEL}[/dim]",
            border_style="yellow",
        )
    )
    console.print()


def print_llm_input(prompt: str) -> None:
    """Print the outgoing prompt in a grey bordered panel with the USER role label."""
    indent = " " * (len("USER") + 2)
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent=indent)
    content = Text.assemble(("USER: ", "bold blue"), (wrapped, "blue"))
    console.print(
        Panel(
            content,
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def print_llm_response(
    response_text: str, mode: str, ttft: float, total_time: float
) -> None:
    """Print the model response and timing stats.

    Truncates very long responses to 400 chars so the terminal stays readable.
    mode is either 'streaming' or 'non-streaming', used for color coding.
    """
    # Truncate long responses so the terminal output stays readable
    display = response_text[:400] + "..." if len(response_text) > 400 else response_text
    wrapped = textwrap.fill(display, width=82, subsequent_indent="           ")
    response_content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))
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

    mode_color = "cyan" if mode == "streaming" else "magenta"

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Metric", style="bold", min_width=32)
    table.add_column("Value", justify="center")

    table.add_row("Mode", f"[{mode_color}]{mode}[/{mode_color}]")
    table.add_row("Time to First Token (TTFT)", f"[green]{ttft:.3f}s[/green]")
    table.add_row("Total Latency", f"[yellow]{total_time:.3f}s[/yellow]")

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the main demo UI."""
    return render_template("index.html")


@app.route("/chat/no-stream", methods=["POST"])
def chat_no_stream():
    """Call the model without streaming and return the full response as JSON.

    TTFT equals total latency here because the client receives nothing until
    the model finishes generating every token.
    Returns a JSON object with keys: text, ttft, total_time.
    """
    data = request.get_json()
    prompt = data.get("prompt", "")

    console.print(
        Rule("[bold magenta]-- Non-Streaming Request --[/bold magenta]", style="white")
    )
    console.print()
    print_llm_input(prompt)

    start = time.perf_counter()
    response = client.models.generate_content(model=MODEL, contents=prompt)
    total_time = time.perf_counter() - start

    # In non-streaming mode the first visible token arrives with the last:
    # TTFT = total latency from the user's perspective.
    ttft = total_time
    response_text = response.text

    print_llm_response(response_text, "non-streaming", ttft, total_time)

    return {"text": response_text, "ttft": ttft, "total_time": total_time}


@app.route("/chat/stream")
def chat_stream():
    """Call the model with streaming and push each token chunk via Server-Sent Events.

    The SSE stream emits two event types:
      - {"type": "token", "token": "...", "ttft": float}  — first chunk only includes ttft
      - {"type": "token", "token": "..."}                 — subsequent chunks
      - {"type": "done",  "total_time": float, "ttft": float}

    TTFT is measured server-side from request receipt to the first non-empty chunk.
    """
    prompt = request.args.get("prompt", "")

    console.print(Rule("[bold cyan]-- Streaming Request --[/bold cyan]", style="white"))
    console.print()
    print_llm_input(prompt)

    def generate():
        """Generator that yields SSE-formatted events for each token from the model."""
        start = time.perf_counter()
        ttft = None
        full_text: list[str] = []

        for chunk in client.models.generate_content_stream(
            model=MODEL, contents=prompt
        ):
            if not chunk.text:
                # Skip empty chunks that can appear between content parts
                continue

            if ttft is None:
                # Capture the moment the very first token arrives
                ttft = time.perf_counter() - start
                payload = {"type": "token", "token": chunk.text, "ttft": ttft}
            else:
                payload = {"type": "token", "token": chunk.text}

            yield f"data: {json.dumps(payload)}\n\n"
            full_text.append(chunk.text)

        total_time = time.perf_counter() - start
        print_llm_response("".join(full_text), "streaming", ttft or 0.0, total_time)

        done_payload = {"type": "done", "total_time": total_time, "ttft": ttft or 0.0}
        yield f"data: {json.dumps(done_payload)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Disable nginx/proxy buffering so tokens reach the browser immediately
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    print_startup_header()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
