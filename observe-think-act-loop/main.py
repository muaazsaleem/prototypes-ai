import os
import subprocess
import sys
import textwrap
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Load environment variables (e.g. OPENROUTER_API_KEY) from the nearest .env,
# walking up from this file so the repo-root .env is picked up.
load_dotenv()

# Initialize Rich Console
console = Console()

# Configuration
FILE_TO_FIX = "broken_code.py"
MODEL_ID = "google/gemini-2.5-flash"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def show_header():
    console.print(
        Panel.fit(
            "[bold yellow]OTA Fix-It Debugger[/bold yellow]\n"
            "[dim]Autonomous Observe-Think-Act loop for code repair.[/dim]",
            border_style="yellow",
        )
    )
    console.print()

def observe():
    """Step 1: Capture the current state (code and error)."""
    console.print(Rule("[bold]Phase: OBSERVE[/bold]", style="white"))
    console.print(f"  [dim]Running {FILE_TO_FIX}...[/dim]")
    
    with open(FILE_TO_FIX, "r") as f:
        code = f.read()
        
    try:
        result = subprocess.run(
            [sys.executable, FILE_TO_FIX], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        if result.returncode == 0:
            return code, None, result.stdout
        else:
            # Combine stdout and stderr for better context
            error_msg = result.stderr if result.stderr else result.stdout
            return code, error_msg, result.stdout
            
    except Exception as e:
        return code, str(e), ""

def think(code, error):
    """Step 2: Reason about the error using Gemini."""
    console.print(Rule("[bold]Phase: THINK[/bold]", style="white"))
    
    # Display Model Input
    input_elements = [
        Text.assemble(("USER: ", "bold blue"), (f"Fix the following code which failed with error:\n{error}", "blue")),
        Rule(style="bright_black"),
        Text.assemble(("CODE:\n", "dim"), (code, "dim"))
    ]
    
    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

    prompt = f"""
    You are an expert Python debugger. 
    The following code is broken:
    
    ```python
    {code}
    ```
    
    It produced the following error:
    ```
    {error}
    ```
    
    Analyze the error and provide the COMPLETE fixed code. 
    Output ONLY the code inside triple backticks. Do not provide explanations.
    """
    
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )

    fixed_code = response.choices[0].message.content
    if "```python" in fixed_code:
        fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
    elif "```" in fixed_code:
        fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
    else:
        fixed_code = fixed_code.strip()
        
    # Display Model Response
    wrapped_response = textwrap.fill("Fixed code generated successfully.", width=82)
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
    
    return fixed_code

def act(fixed_code):
    """Step 3: Apply the fix to the environment."""
    console.print(Rule("[bold]Phase: ACT[/bold]", style="white"))
    console.print(f"  [dim]Applying changes to {FILE_TO_FIX}...[/dim]")
    with open(FILE_TO_FIX, "w") as f:
        f.write(fixed_code)
    console.print("  [bold green]✓ File updated.[/bold green]")
    console.print()

def run_ota_loop():
    show_header()
    
    max_iterations = 3
    for i in range(max_iterations):
        console.print(f"[bold cyan]-- Iteration {i+1} --------------------------------------[/bold cyan]")
        
        code, error, stdout = observe()
        
        if error is None:
            console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
            console.print("\n[bold green]✅ Success: Code is now working correctly![/bold green]")
            console.print(Panel(stdout.strip(), title="Output", border_style="green"))
            return
            
        console.print(f"\n[bold red]❌ Failure detected:[/bold red]")
        console.print(Panel(error.strip(), border_style="red", title="Traceback"))
        console.print()
        
        fixed_code = think(code, error)
        act(fixed_code)
    
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print("\n[bold red]Limits reached. Could not fix the code in 3 iterations.[/bold red]")

if __name__ == "__main__":
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)
    
    try:
        run_ota_loop()
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {str(e)}")
        sys.exit(1)
