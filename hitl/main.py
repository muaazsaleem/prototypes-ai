from typing import Literal
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

class SafeCommandRunner:
    """Manages secure command execution and human approval state for system metrics."""
    
    def __init__(self, history_list=None):
        # State to keep track of human approved commands in the current session
        self.approved_commands = set()
        self.history = history_list if history_list is not None else []

    def log_tool_call(self, function_name: str, args: dict):
        """Logs the model's intent to execute a function along with its arguments."""
        console.print(Rule("[bold bright_black]Model Tool Call[/bold bright_black]", style="bright_black"))
        console.print()
        console.print(f"  [bold yellow]Function:[/bold yellow] [bold green]{function_name}[/bold green]")
        console.print(f"  [bold yellow]Arguments:[/bold yellow]")
        for k, v in args.items():
            console.print(f"    [cyan]{k}:[/cyan] {v}")
        console.print()
        
        # Format arguments for display in conversation history
        args_str = ", ".join([f"{k}='{v}'" for k, v in args.items()])
        self.history.append({"role": "assistant", "content": f"call:{function_name}({args_str})"})

    def request_human_approval(self, command: str, reason: str) -> str:
        """Requests approval from a human operator before executing a shell command.

        You MUST invoke this tool and receive an 'Approved' response before you can execute any shell command.

        Args:
            command: The exact shell command that requires human approval (e.g., 'df -h', 'uptime', 'free -m').
            reason: The logical reason why executing this command is necessary.
        """
        self.log_tool_call("request_human_approval", {"command": command, "reason": reason})
        
        console.print(Rule("[bold yellow]Human Approval Requested[/bold yellow]", style="yellow"))
        console.print()
        console.print(f"  [bold cyan]AI Action:[/bold cyan] execute_command")
        console.print(f"  [bold cyan]Command:  [/bold cyan] [yellow]{command}[/yellow]")
        
        wrapped_reason = textwrap.fill(reason, width=80, subsequent_indent="            ")
        console.print(f"  [bold cyan]Reason:   [/bold cyan] {wrapped_reason}")
        
        user_answer = console.input("\n  [bold blue]Approve this command? (y/n / exit): [/bold blue]").strip().lower()
        
        if user_answer == 'exit':
            console.print("  [bold red]Session terminated.[/bold red]")
            sys.exit(0)
            
        approved = user_answer in ('y', 'yes')
        if approved:
            self.approved_commands.add(command)
            console.print(f"  [bold green]Verdict:  Approved by human.[/bold green]")
            console.print()
            self.history.append({"role": "tool", "content": "Approved"})
            return "Approved: The human operator has approved this action. You may now proceed to execute it."
        else:
            console.print(f"  [bold red]Verdict:  Rejected by human.[/bold red]")
            console.print()
            self.history.append({"role": "tool", "content": "Rejected"})
            return "Rejected: The human operator has denied this action. You must not execute it."

    def execute_command(self, command: str, reason: str) -> str:
        """Executes a shell command to gather OS metrics or perform system tasks.

        CRITICAL: You MUST ask for and obtain human approval via the 'request_human_approval' tool
        BEFORE calling this tool. You are strictly forbidden from calling execute_command
        unless the human operator has already explicitly approved the command execution.

        Args:
            command: The exact shell command to execute (e.g., 'df -h', 'free -m', 'uptime').
            reason: The logical reason why this command needs to be executed.
        """
        self.log_tool_call("execute_command", {"command": command, "reason": reason})
        
        if command in self.approved_commands:
            console.print(Rule("[bold green]Executing Approved Command[/bold green]", style="green"))
            console.print()
            console.print(f"  [bold cyan]Command:[/bold cyan] [yellow]{command}[/yellow]")
            
            try:
                import subprocess
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    console.print(f"  [bold green]Status:  Success[/bold green]")
                    
                    output_text = result.stdout or "[No stdout]"
                    console.print(Panel(output_text, title="[bold dim]Command Output[/bold dim]", border_style="dim"))
                    console.print()
                    self.history.append({"role": "tool", "content": f"Success: {result.stdout}"})
                    return f"Success: Command output:\n{result.stdout}"
                else:
                    console.print(f"  [bold red]Status:  Failed (Exit Code {result.returncode})[/bold red]")
                    
                    error_text = result.stderr or "[No stderr]"
                    console.print(Panel(error_text, title="[bold red]Command Error[/bold red]", border_style="red"))
                    console.print()
                    self.history.append({"role": "tool", "content": f"Failed: {result.stderr}"})
                    return f"Error: Command failed with exit code {result.returncode}.\nStderr: {result.stderr}"
            except Exception as e:
                console.print(f"  [bold red]Exception occurred during command execution: {e}[/bold red]")
                console.print()
                self.history.append({"role": "tool", "content": f"Error: Exception: {str(e)}"})
                return f"Error: Failed to execute command. Exception: {str(e)}"
        else:
            console.print(Rule("[bold red]Unapproved Command Attempted[/bold red]", style="red"))
            console.print()
            console.print(f"  [bold red]Attempted to execute command '{command}' without prior human approval![/bold red]")
            console.print()
            self.history.append({"role": "tool", "content": "Blocked: Unapproved"})
            return (
                f"Error: Command execution rejected. You did not obtain explicit human approval for "
                f"executing '{command}' before calling execute_command. You must first call "
                f"request_human_approval and obtain approval."
            )

def get_client() -> genai.Client:
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
            "[bold yellow]HITL Safe Command Runner[/bold yellow]\n"
            "[dim]A simplified Human-in-the-loop prototype demonstrating secure, approved shell execution.[/dim]\n"
            "[dim]Model: gemini-2.5-flash[/dim]",
            border_style="yellow",
        )
    )
    console.print()

def display_model_input(messages_list):
    """Displays the conversation messages in a styled Panel as specified in terminal-output-style."""
    input_elements = []
    for msg in messages_list:
        role = msg["role"]
        content = msg["content"]
        
        if role == "system":
            label_style = "dim"
            content_style = "dim"
        elif role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "assistant":
            if content.startswith("call:"):
                label_style = "bold yellow"
                content_style = "yellow"
            else:
                label_style = "bold green"
                content_style = "green"
        elif role == "tool":
            label_style = "bold yellow"
            content_style = "yellow"
        else:
            label_style = "bold"
            content_style = "white"
        
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        
        input_elements.append(Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style)))
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop() # Remove trailing rule

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

def display_model_output(response_text: str):
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
    """Main HITL loop using Automatic Function Calling (Tools)."""
    client = get_client()
    model_id = "gemini-2.5-flash"
    
    history_for_display = []
    runner = SafeCommandRunner(history_for_display)
    display_header()
    
    # Prompt the user for what they want to achieve on the system
    console.print("[bold cyan]What would you like the AI agent to do on this system?[/bold cyan]")
    console.print("[dim]Example: 'check current memory and cpu information' or 'find files larger than 10MB'[/dim]")
    user_goal = console.input("\n[bold blue]Objective: [/bold blue]").strip()
    
    if not user_goal:
        console.print("\n[bold red]Error: Objective cannot be empty.[/bold red]")
        sys.exit(1)
        
    console.print()
    
    current_input = (
        f"The user wants you to achieve the following objective on their system: '{user_goal}'.\n\n"
        "Analyze this objective, determine what shell commands are needed, and execute them. "
        "Remember, you are strictly required to ask for human approval before executing any shell command!"
    )
    
    system_instruction = (
        "You are an automated system administrator. Your task is to fulfill the user's objective by executing shell commands.\n\n"
        "STRICT PROTOCOLS:\n"
        "1. Identify the appropriate shell commands needed to achieve the user's objective.\n"
        "2. Before running ANY command via 'execute_command', you MUST first request human approval using the 'request_human_approval' tool.\n"
        "3. Only if the human operator explicitly approves a command (returns 'Approved...'), you may proceed to call the 'execute_command' tool.\n"
        "4. Calling 'execute_command' without first obtaining human approval is strictly forbidden.\n"
        "5. Once you have successfully executed the commands, present a neat summary of the results back to the user."
    )
    
    history_for_display.append({"role": "system", "content": system_instruction})
    history_for_display.append({"role": "user", "content": current_input})
    
    # Initialize chat session with Python methods as tools
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[runner.request_human_approval, runner.execute_command],
            temperature=0.0,
        )
    )
    
    console.print(Rule("[bold]AI Session Started[/bold]", style="white"))
    console.print()
    
    user_message = current_input
    while True:
        # Display the complete context before sending
        display_model_input(history_for_display)
        
        try:
            response = chat.send_message(user_message)
            content = response.text or "[No text provided]"
            history_for_display.append({"role": "assistant", "content": content})
            display_model_output(content)
        except Exception as e:
            console.print(f"[bold red]API Error:[/bold red] {e}")
            break
            
        try:
            user_message = console.input("[bold blue]You: [/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Session terminated.[/bold red]")
            break
            
        if not user_message:
            console.print("[bold red]Session finished.[/bold red]")
            break
            
        if user_message.lower() in ('exit', 'quit'):
            console.print("[bold red]Session terminated.[/bold red]")
            break
            
        console.print()
        history_for_display.append({"role": "user", "content": user_message})

if __name__ == "__main__":
    try:
        run_hitl_session()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user.[/bold red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)
