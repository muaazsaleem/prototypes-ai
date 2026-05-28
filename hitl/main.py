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
            "[bold yellow]HITL Content Refiner[/bold yellow]\n"
            "[dim]A Human-in-the-loop prototype for iterative content creation with LLMs.[/dim]\n"
            "[dim]Model: gemini-2.0-flash[/dim]",
            border_style="yellow",
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
    model_id = "gemini-2.5-flash" # Updated to the requested 2.5-flash version
    
    # Explicit tool definition as a dictionary/schema
    tool_schema = {
        "function_declarations": [
            {
                "name": "request_human_input",
                "description": "Asks the human user a specific question to clarify details or get missing information.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "question": {
                            "type": "STRING",
                            "description": "The specific question or clarification needed from the human."
                        }
                    },
                    "required": ["question"]
                }
            }
        ]
    }
    
    system_instruction = (
        "You are a professional content architect. Your goal is to produce accurate, high-quality content.\n\n"
        "STRICT PROTOCOL:\n"
        "1. If you are missing ANY facts (names, dates, titles, etc.), you MUST call the 'request_human_input' tool. "
        "Do not provide a draft with placeholders.\n"
        "2. Once you have all the facts, provide the full content.\n"
        "3. When finished, append 'FINAL_COMPLETE_DRAFT' to the end of your message."
    )
    
    display_header()
    
    # Automated Task for demonstration
    current_input = "Draft a formal Security Incident Report for a suspected database breach."
    console.print(f"[bold cyan]Auto-starting with task:[/bold cyan] {current_input}\n")
    
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
        
        # Display history
        history = chat.get_history()
        if history:
            display_model_input(history)
        
        try:
            response = chat.send_message(current_input)
        except Exception as e:
            console.print(f"[bold red]API Error:[/bold red] {e}")
            break

        # Check for Tool Calls (Function Calls)
        function_calls = response.function_calls
        if function_calls:
            for call in function_calls:
                if call.name == "request_human_input":
                    question = call.args.get("question", "What info is needed?")
                    
                    console.print(Rule("[bold yellow]Human Input Requested[/bold yellow]", style="yellow"))
                    console.print(f"[bold cyan]AI Question:[/bold cyan] {question}")
                    
                    user_answer = console.input("\n[bold blue]> Your Answer: [/bold blue]").strip()
                    
                    if user_answer.lower() == 'exit':
                        console.print("[bold red]Session terminated.[/bold red]")
                        return

                    # Return tool response
                    current_input = types.Part.from_function_response(
                        name="request_human_input",
                        response={"result": user_answer}
                    )
            continue

        # Handle text response
        content = response.text or "[No text provided]"
        display_model_output(content)
        
        if "FINAL_COMPLETE_DRAFT" in content.upper():
            console.print(Rule("[bold green]Content Approved[/bold green]", style="green"))
            break
        
        choice = console.input("\n[bold blue]> Feedback / Continue (or 'exit'): [/bold blue]").strip()
        if choice.lower() == 'exit':
            break
        current_input = choice if choice else "Finalize the draft."

if __name__ == "__main__":
    try:
        run_hitl_session()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user.[/bold red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)
