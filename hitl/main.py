import os
import sys
import textwrap
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from google import genai
from google.genai import types

# Initialize rich console
console = Console()

# Simulated file system
SIMULATED_FILES = {
    "report_2025.txt": {"size": "1.2 MB", "type": "Document", "description": "Annual security and performance report."},
    "temp_cache_001.tmp": {"size": "45 KB", "type": "Temporary", "description": "Temporary cache file from previous session."},
    "old_draft.bak": {"size": "120 KB", "type": "Backup", "description": "Backup of an old document draft from 2024."},
    "system_config.json": {"size": "8 KB", "type": "Configuration", "description": "Important system settings."}
}

# Global state to keep track of human approvals in the current session
APPROVED_FILES = set()

def get_client():
    """Returns a google-genai client or exits if API key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set.")
        console.print("Please set it with: [bold]export GEMINI_API_KEY='your-api-key'[/bold]")
        sys.exit(1)
    return genai.Client(api_key=api_key)

def display_header():
    """Displays the application header."""
    console.print(
        Panel.fit(
            "[bold red]HITL Safe File Cleaner[/bold red]\n"
            "[dim]A simplified Human-in-the-loop prototype demonstrating safe deletion.[/dim]\n"
            "[dim]Model: gemini-2.5-flash[/dim]",
            border_style="red",
        )
    )
    console.print()

def display_model_output(response_text):
    """Displays the model's response in a styled panel."""
    if not response_text or response_text == "[No text provided]":
        return

    wrapped_response = textwrap.fill(response_text, width=82, subsequent_indent="           ")
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"),
        (wrapped_response, "italic")
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

def request_human_approval(action: str, filename: str, reason: str) -> str:
    """Requests approval from a human operator before taking critical actions.

    You MUST invoke this tool and receive an 'Approved' response before you can delete any file.

    Args:
        action: The action that requires human approval (e.g., 'delete_file').
        filename: The file involved in the action.
        reason: The logical reason why this action is necessary.
    """
    console.print(Rule("[bold yellow]Human Approval Requested[/bold yellow]", style="yellow"))
    console.print(f"[bold cyan]AI requests approval to perform action:[/bold cyan] [yellow]{action}[/yellow]")
    console.print(f"[bold cyan]Target File:[/bold cyan] [yellow]{filename}[/yellow]")
    console.print(f"[bold cyan]Reason:[/bold cyan] {reason}")
    
    user_answer = console.input("\n[bold blue]Approve this request? (y/n / exit): [/bold blue]").strip().lower()
    
    if user_answer == 'exit':
        console.print("[bold red]Session terminated.[/bold red]")
        sys.exit(0)
        
    approved = user_answer in ('y', 'yes')
    if approved:
        APPROVED_FILES.add(filename)
        console.print(f"[bold green]Action approved by human.[/bold green]\n")
        return "Approved: The human operator has approved this action. You may now proceed to execute it."
    else:
        console.print(f"[bold red]Action rejected by human.[/bold red]\n")
        return "Rejected: The human operator has denied this action. You must not execute it."

def delete_file(filename: str, reason: str) -> str:
    """Deletes a file from the system.

    CRITICAL: You MUST ask for and obtain human approval via the 'request_human_approval' tool
    BEFORE calling this tool. You are strictly forbidden from calling delete_file
    unless the human operator has already explicitly approved the deletion.

    Args:
        filename: The name of the file to delete.
        reason: The logical reason why this file should be deleted.
    """
    if filename in APPROVED_FILES:
        if filename in SIMULATED_FILES:
            SIMULATED_FILES[filename]["deleted"] = True
            console.print(f"[bold green]File '{filename}' has been successfully deleted.[/bold green]\n")
            return f"Success: File '{filename}' deleted."
        else:
            console.print(f"[bold red]File '{filename}' not found.[/bold red]\n")
            return f"Error: File '{filename}' not found."
    else:
        console.print(f"[bold red]Attempted to delete '{filename}' without prior human approval![/bold red]\n")
        return (
            f"Error: Deletion rejected. You did not obtain explicit human approval for "
            f"deleting '{filename}' before calling delete_file. You must first call "
            f"request_human_approval and obtain approval."
        )

def run_hitl_session():
    """Main HITL loop using Automatic Function Calling (Tools)."""
    client = get_client()
    model_id = "gemini-2.5-flash"
    
    # Reset local state
    APPROVED_FILES.clear()
    for name in SIMULATED_FILES:
        SIMULATED_FILES[name].pop("deleted", None)
        
    display_header()
    
    # Display initial state of the simulated files
    console.print("[bold yellow]Initial File System State:[/bold yellow]")
    for name, info in SIMULATED_FILES.items():
        console.print(f"- [cyan]{name}[/cyan]: {info['type']} ({info['size']}) - {info['description']}")
    console.print()
    
    # Format the file list for the prompt
    file_list_str = "\n".join(
        [f"- {name}: {info['type']} ({info['size']}) - {info['description']}" for name, info in SIMULATED_FILES.items()]
    )
    
    current_input = (
        f"Please analyze and clean up the following simulated files. Identify obsolete, temporary, "
        f"or backup files and delete them. Here are the files:\n\n{file_list_str}"
    )
    
    system_instruction = (
        "You are an automated file cleanup assistant. Your task is to process a list of files, "
        "analyze which ones are temporary or obsolete, and delete them.\n\n"
        "STRICT PROTOCOLS:\n"
        "1. For each file, analyze whether it should be kept or deleted.\n"
        "2. If you decide to delete a file, you MUST first request human approval using the 'request_human_approval' tool.\n"
        "3. Only if the human operator explicitly approves the request (returns 'Approved...'), you may proceed to "
        "call the 'delete_file' tool to delete that specific file. Deleting a file without first obtaining human approval is strictly forbidden.\n"
        "4. Once you have processed all files, present a summary of what was kept and what was deleted."
    )
    
    # Initialize chat session with Python functions as tools
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[request_human_approval, delete_file],
            temperature=0.0,
        )
    )
    
    console.print(Rule("[bold]AI Processing[/bold]", style="white"))
    try:
        response = chat.send_message(current_input)
        content = response.text or "[No text provided]"
        display_model_output(content)
    except Exception as e:
        console.print(f"[bold red]API Error:[/bold red] {e}")
        
    # Display final state of simulated files
    console.print()
    console.print(Rule("[bold green]Final Simulated File System Status[/bold green]", style="green"))
    for name, info in SIMULATED_FILES.items():
        status = "[bold red]DELETED[/bold red]" if info.get("deleted") else "[bold green]KEPT[/bold green]"
        console.print(f"- [cyan]{name}[/cyan]: {status} ({info['type']})")
    console.print()

if __name__ == "__main__":
    try:
        run_hitl_session()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user.[/bold red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)
