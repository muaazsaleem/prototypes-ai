import os
import sys
import textwrap
import subprocess
import re
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize Rich Console
console = Console()

class PatchAgent:
    def __init__(self, api_key=None):
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-flash"

    def clean_patch(self, text):
        # Remove markdown code blocks if present
        match = re.search(r"```(?:diff)?\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1)
        return text.strip()

    def analyze_file(self, file_path):
        console.print(f"[dim]Reading {file_path} from disk...[/dim]")
        with open(file_path, "r") as f:
            lines = f.readlines()
            content = "".join(lines)
        
        console.print(f"[dim]File contains {len(lines)} lines.[/dim]")
        
        # System instructions to ensure minimal output and correct format
        prompt = f"""
        You are an expert Python engineer. Analyze the provided code and identify ONE specific bug, anti-pattern, or improvement.
        
        Constraints:
        1. Fix ONLY ONE thing per iteration.
        2. Provide the fix in UNIFIED DIFF format for the file "{file_path}".
        3. Do NOT include any explanation, talk, or markdown code blocks outside of the diff itself.
        4. The diff MUST be valid and apply cleanly to the current file.
        5. Use "--- a/{file_path}" and "+++ b/{file_path}" as headers.
        6. Provide exactly 3 lines of context around changes.
        7. DO NOT USE PLACEHOLDERS like "..." or "unchanged code".
        8. Pay attention to indentation; it must match the original file exactly.

        EXAMPLE VALID DIFF:
        --- a/{file_path}
        +++ b/{file_path}
        @@ -1,5 +1,5 @@
         import os
        -import old_lib
        +import new_lib
         
         def func():
             print("test")

        FILE CONTENT TO ANALYZE:
        ```python
        {content}
        ```
        """
        
        console.print(f"[bold cyan]-- Analyzing {file_path} --------------------------------------[/bold cyan]")
        
        # Displaying Model Input (per skill)
        messages = [{"role": "user", "content": prompt}]
        input_elements = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            label_style = "bold blue" if role == "user" else "dim"
            content_style = "blue" if role == "user" else "dim"
            input_elements.append(Text.assemble((f"{role.upper()}: ", label_style), (content, content_style)))
        
        console.print(Panel(Group(*input_elements), title="[bold bright_black]Model Input[/bold bright_black]", border_style="bright_black", padding=(1, 2)))

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        
        raw_output = response.text
        # Displaying Model Output (per skill) - NO WRAP for code
        response_content = Text.assemble(("ASSISTANT: ", "bold green"), (raw_output, "italic"))
        console.print(Panel(response_content, title="[bold bright_black]Model Response[/bold bright_black]", border_style="bright_black", padding=(1, 2), highlight=False))
        
        return self.clean_patch(raw_output)

    def apply_patch(self, file_path, patch_text):
        patch_file = "temp.patch"
        with open(patch_file, "w") as f:
            f.write(patch_text)
        
        try:
            # Try 'git apply' first for clean staging
            result = subprocess.run(["git", "apply", patch_file], capture_output=True, text=True)
            if result.returncode == 0:
                console.print(f"[bold green]Patch applied successfully via git apply.[/bold green]")
            else:
                # Fallback to standard 'patch' command which is more lenient
                result = subprocess.run(["patch", "-u", file_path, "-i", patch_file], capture_output=True, text=True)
                if result.returncode == 0:
                    console.print(f"[bold yellow]Patch applied via fallback 'patch' command.[/bold yellow]")
                else:
                    console.print(f"[bold red]Error applying patch:[/bold red] {result.stderr}")
                    return False
            
            # Stage the change
            subprocess.run(["git", "add", file_path])
            return True
        finally:
            if os.path.exists(patch_file):
                os.remove(patch_file)

def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set.")
        return

    agent = PatchAgent(api_key=api_key)
    
    console.print(
        Panel.fit(
            "[bold yellow]Code Patcher Agent[/bold yellow]\n"
            "[dim]Autonomous incremental patching[/dim]\n"
            "[dim]Mode: Direct File Update / Git-Staged[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    target_file = "buggy_app.py"
    
    for i in range(20): # Limit to 20 iterations
        console.print(Rule(f"[bold]Iteration {i+1}[/bold]", style="white"))
        patch = agent.analyze_file(target_file)
        
        if not patch or "---" not in patch or "No changes" in patch:
            console.print("[bold green]No more bugs detected or invalid patch. Finishing loop.[/bold green]")
            break

        if agent.apply_patch(target_file, patch):
            console.print(f"[bold cyan]Iteration {i+1} complete. File updated and staged.[/bold cyan]")
        else:
            console.print("[bold red]Failed to apply patch in this iteration.[/bold red]")
        
        console.print()

    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    
    table = Table(title="Patching Results", show_lines=True)
    table.add_column("Iteration", justify="center", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Patch Applied", justify="center")
    
if __name__ == "__main__":
    main()
