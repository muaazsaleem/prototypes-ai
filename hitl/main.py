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

def display_model_input(history):
    """Displays the chat history in a styled panel, skipping tool internal parts."""
    if not history:
        return
        
    input_elements = []
    for msg in history:
        role = msg.role
        # Filter for text parts only to avoid showing tool-call metadata in the UI
        content_parts = [part.text for part in msg.parts if part.text]
        if not content_parts:
            continue
            
        content = "".join(content_parts)
        
        if role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "model":
            label_style = "bold green"
            content_style = "green"
        else:
            label_style = "dim"
            content_style = "dim"
        
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        
        input_elements.append(Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style)))
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop() # Remove trailing rule
        console.print(
            Panel(
                Group(*input_elements),
                title="[bold bright_black]Conversation History[/bold bright_black]",
                border_style="bright_black",
                padding=(1, 2),
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

def run_hitl_session():
    """Main HITL loop using Function Calling (Tools)."""
    client = get_client()
    model_id = "gemini-2.5-flash"
    
    # Explicit tool definition with requested confirmation phrase
    tool_schema = {
        "function_declarations": [
            {
                "name": "delete_file",
                "description": "Deletes a file from the system. Invoke when you decide to take this action.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "filename": {
                            "type": "STRING",
                            "description": "The name of the file to delete."
                        },
                        "reason": {
                            "type": "STRING",
                            "description": "The logical reason why this file should be deleted."
                        }
                    },
                    "required": ["filename", "reason"]
                }
            }
        ]
    }
    
    # System instruction with requested confirmation phrase
    system_instruction = (
        "You are an automated file cleanup assistant. Your task is to process a list of files, "
        "analyze which ones are temporary or obsolete, and delete them.\n\n"
        "STRICT PROTOCOLS:\n"
        "1. For each file, analyze whether it should be kept or deleted.\n"
        "2. If you decide to delete a file, you MUST use the 'delete_file' tool. "
        "Invoke when you decide to take this action.\n"
        "3. Once you have processed all files, present a summary of what was kept and what was deleted."
    )
    
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
    
    # Initialize chat session with tools
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[tool_schema],
            temperature=0.0,
        )
    )
    
    while True:
        console.print(Rule("[bold]AI Processing[/bold]", style="white"))
        
        try:
            response = chat.send_message(current_input)
        except Exception as e:
            console.print(f"[bold red]API Error:[/bold red] {e}")
            break

        # Check for Tool Calls (Function Calls)
        function_calls = response.function_calls
        if function_calls:
            tool_responses = []
            for call in function_calls:
                if call.name == "delete_file":
                    filename = call.args.get("filename")
                    reason = call.args.get("reason", "No reason provided.")
                    
                    console.print(Rule("[bold yellow]Human Approval Requested[/bold yellow]", style="yellow"))
                    console.print(f"[bold cyan]AI wishes to delete:[/bold cyan] [yellow]{filename}[/yellow]")
                    console.print(f"[bold cyan]Reason:[/bold cyan] {reason}")
                    
                    user_answer = console.input("\n[bold blue]Approve deletion? (y/n / exit): [/bold blue]").strip().lower()
                    
                    if user_answer == 'exit':
                        console.print("[bold red]Session terminated.[/bold red]")
                        return
                    
                    approved = user_answer in ('y', 'yes')
                    if approved:
                        if filename in SIMULATED_FILES:
                            SIMULATED_FILES[filename]["deleted"] = True
                            result = f"Success: File '{filename}' deleted."
                            console.print(f"[bold green]File '{filename}' has been successfully deleted.[/bold green]\n")
                        else:
                            result = f"Error: File '{filename}' not found."
                            console.print(f"[bold red]File '{filename}' not found.[/bold red]\n")
                    else:
                        result = f"Rejected: Human user refused deletion of '{filename}'."
                        console.print(f"[bold red]Deletion of '{filename}' was rejected by the human user.[/bold red]\n")
                    
                    tool_responses.append(
                        types.Part.from_function_response(
                            name="delete_file",
                            response={"result": result}
                        )
                    )
            
            # Send the tool response(s) back to the model
            current_input = tool_responses
            continue

        # Handle final text response
        content = response.text or "[No text provided]"
        display_model_output(content)
        break

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
