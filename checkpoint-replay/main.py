#!/usr/bin/env python3
"""
Resumable Conversational AI Agent with Per-Session JSON Checkpointing

This program demonstrates a conversational agent that:
  1. Manages multiple concurrent conversation/session histories.
  2. Saves the state of every turn (both user query and model response)
     into a dedicated JSON file per session (checkpoint_<session_id>.json).
  3. Restores the complete conversation history of a selected session
     by loading its dedicated JSON file and replaying the state.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from google import genai
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_NAME = "gemini-2.5-flash"

# ── LLM Client Initialization ──────────────────────────────────────────────────

_client: genai.Client | None = None


def get_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Call configure_client() before running the agent.")
    return _client


def configure_client(api_key: str) -> None:
    global _client
    _client = genai.Client(api_key=api_key)


# ── Checkpoint Management ───────────────────────────────────────────────────────


def get_session_file_path(session_id: str) -> Path:
    """Returns the dedicated JSON file path for a session ID."""
    return Path(f"checkpoint_{session_id}.json")


def load_all_sessions() -> dict[str, dict]:
    """
    Scans the current directory for session files (checkpoint_*.json).
    Loads and parses each file to reconstruct active sessions.
    
    Returns:
        dict: A map of session_id -> {"history": [...], "updated_at": "..."}
    """
    sessions = {}
    for path in Path(".").glob("checkpoint_*.json"):
        try:
            session_id = path.stem.replace("checkpoint_", "")
            if not session_id:
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions[session_id] = {
                    "history": data.get("history", []),
                    "updated_at": data.get("updated_at", ""),
                }
        except (json.JSONDecodeError, IOError):
            # Ignore malformed or unreadable files
            continue
    return sessions


def checkpoint_session(session_id: str, history: list[dict]) -> None:
    """
    Saves the entire conversation history of a session into its dedicated JSON file.
    Overwrites the file on every message to ensure immediate persistence.
    """
    file_path = get_session_file_path(session_id)
    data = {
        "session_id": session_id,
        "history": history,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        console.print(f"[red]Error saving checkpoint for session '{session_id}': {e}[/red]")


def delete_session_checkpoint(session_id: str) -> None:
    """Deletes the dedicated JSON file of a session."""
    file_path = get_session_file_path(session_id)
    if file_path.exists():
        try:
            file_path.unlink()
        except IOError as e:
            console.print(f"[red]Error deleting checkpoint for session '{session_id}': {e}[/red]")


# ── Display Helpers ────────────────────────────────────────────────────────────


def print_message(role: str, text: str) -> None:
    """Renders user and model messages in clean, stylized panels."""
    if role == "user":
        border_style = "blue"
        title = "[bold blue]User[/bold blue]"
        content = text
    else:
        border_style = "green"
        title = "[bold green]Gemini[/bold green]"
        content = Markdown(text)

    console.print(
        Panel(
            content,
            title=title,
            border_style=border_style,
            padding=(1, 2),
        )
    )
    console.print()


def list_sessions_table(sessions: dict[str, dict]) -> None:
    """Displays a beautifully formatted table of all saved conversational sessions."""
    if not sessions:
        console.print("[yellow]No saved sessions found.[/yellow]")
        return
        
    table = Table(title="Saved Conversational Sessions", border_style="cyan")
    table.add_column("Session ID", style="bold yellow")
    table.add_column("Turn Count", justify="right", style="green")
    table.add_column("Last Updated", style="dim")
    table.add_column("Preview of Last Message", style="italic")

    for session_id, data in sessions.items():
        history = data.get("history", [])
        updated_at = data.get("updated_at", "Unknown")
        
        turn_count = len(history)
        
        preview = ""
        if history:
            last_msg = history[-1]
            last_text = last_msg.get("parts", [{}])[0].get("text", "").replace("\n", " ")
            role_prefix = "You: " if last_msg.get("role") == "user" else "Gemini: "
            preview = f"{role_prefix}{last_text}"
            if len(preview) > 60:
                preview = preview[:57] + "..."
        else:
            preview = "(Empty / Reset)"

        formatted_time = updated_at
        try:
            dt = datetime.fromisoformat(updated_at)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

        table.add_row(session_id, str(turn_count), formatted_time, preview)

    console.print(table)


def select_or_create_session(sessions: dict[str, dict]) -> str:
    """Interactively prompts the user to select an existing session or start a new one."""
    if sessions:
        list_sessions_table(sessions)
        console.print("\n[bold cyan]Available Options:[/bold cyan]")
        console.print("  - Type an [bold yellow]existing Session ID[/bold yellow] to resume.")
        console.print("  - Type a [bold green]new Session ID[/bold green] to start a fresh conversation.")
        console.print("  - Press [bold white]Enter[/bold white] to start a new auto-named session.\n")
    else:
        console.print("[yellow]No existing conversational sessions found.[/yellow]")
        console.print("Press [bold white]Enter[/bold white] to start a new session ('session-1'), or type a custom Session ID below.\n")

    while True:
        try:
            session_id = console.input("[bold cyan]Enter Session ID > [/bold cyan]").strip()
            if not session_id:
                i = 1
                while f"session-{i}" in sessions:
                    i += 1
                session_id = f"session-{i}"
            return session_id
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            sys.exit(0)


# ── Conversation Loop ──────────────────────────────────────────────────────────


def run_chat(session_id: str, history: list[dict]) -> None:
    """Enters an interactive loop with the user and Gemini, saving progress after every message."""
    client = get_client()
    
    if history:
        console.print(
            Panel.fit(
                f"[bold cyan]Resuming Session '{session_id}' (Full State Restored)[/bold cyan]\n"
                f"[dim]Replaying {len(history)} messages from history...[/dim]",
                border_style="cyan",
            )
        )
        console.print()
        for msg in history:
            role = msg.get("role", "user")
            parts = msg.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            print_message(role, text)
    else:
        console.print(
            Panel.fit(
                f"[bold yellow]Starting Fresh Session '{session_id}'[/bold yellow]\n"
                "[dim]Type your message below. Commands: '/exit' to quit, '/reset' to start fresh.[/dim]",
                border_style="yellow",
            )
        )
        console.print()

    while True:
        try:
            user_input = console.input("[bold magenta]You > [/bold magenta]").strip()
            if not user_input:
                continue

            # Command Handling
            if user_input.lower() in ("/exit", "/quit"):
                console.print("\n[yellow]Exiting conversational agent. Progress is saved.[/yellow]")
                break

            if user_input.lower() == "/reset":
                console.print(f"\n[yellow]Resetting session '{session_id}'...[/yellow]")
                delete_session_checkpoint(session_id)
                history = []
                console.print(f"[green]Session '{session_id}' reset successfully. Send a message to start fresh![/green]\n")
                continue

            # 1. Add user message to history
            history.append({"role": "user", "parts": [{"text": user_input}]})
            
            # 2. Checkpoint user message "as is" immediately
            checkpoint_session(session_id, history)
            
            # 3. Print the user's message
            print_message("user", user_input)

            # 4. Generate response from model
            with console.status("[bold green]Gemini is thinking...[/bold green]"):
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=history,
                )
                response_text = response.text.strip()

            # 5. Add model response to history
            history.append({"role": "model", "parts": [{"text": response_text}]})
            
            # 6. Checkpoint model response "as is" immediately
            checkpoint_session(session_id, history)

            # 7. Print the model's response
            print_message("model", response_text)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted by user. Progress is saved.[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error calling model:[/bold red] {e}")
            console.print("[yellow]Your inputs are saved. You can retry running the agent.[/yellow]\n")


# ── Entry Point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable Conversational AI Agent with Per-Session JSON Checkpointing",
    )
    parser.add_argument(
        "--session",
        "-s",
        type=str,
        help="The Session ID to resume or create. If omitted, you will be prompted to select/create one.",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all saved sessions and exit",
    )
    parser.add_argument(
        "--reset",
        "-r",
        action="store_true",
        help="Delete all checkpoints or reset a specific session if --session is provided",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set."
        )
        sys.exit(1)

    configure_client(api_key)

    # 1. Handle Reset Actions
    if args.reset:
        if args.session:
            console.print(f"[yellow]Resetting session '{args.session}'...[/yellow]")
            delete_session_checkpoint(args.session)
            console.print(f"[green]Session '{args.session}' has been reset.[/green]")
            if not args.list:
                sys.exit(0)
        else:
            console.print("[yellow]Deleting all checkpoints...[/yellow]")
            deleted_any = False
            for path in Path(".").glob("checkpoint_*.json"):
                path.unlink()
                deleted_any = True
            if deleted_any:
                console.print("[green]All checkpoints successfully cleared.[/green]")
            else:
                console.print("[dim]No checkpoint files found to delete.[/dim]")
            if not args.list:
                sys.exit(0)

    # 2. Handle Listing Actions
    if args.list:
        sessions = load_all_sessions()
        list_sessions_table(sessions)
        sys.exit(0)

    # 3. Load sessions & select session ID
    sessions = load_all_sessions()
    
    if args.session:
        session_id = args.session
    else:
        session_id = select_or_create_session(sessions)

    # 4. Extract active history for selected session
    active_session = sessions.get(session_id, {})
    history = active_session.get("history", [])

    # 5. Run conversational session
    run_chat(session_id, history)


if __name__ == "__main__":
    main()
