import sys
from agent import SelfEvolvingAgent, console
from rich.panel import Panel
from rich.rule import Rule

def main():
    # Print opening header panel using rich styling
    console.print(
        Panel.fit(
            "[bold yellow]🧬 Gemini 2.5 Self-Evolving Agent Prototype[/bold yellow]\n"
            "[dim]An autonomous agent that creates, registers, and executes its own tools on the fly.[/dim]\n"
            "[dim]Powered by Gemini 2.5 Flash & the new google-genai SDK[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # Initialize the self-evolving agent
    try:
        agent = SelfEvolvingAgent()
    except Exception as e:
        console.print(f"[bold red]Error initializing agent:[/bold red] {str(e)}")
        sys.exit(1)

    # The challenge task: Requires terminal/shell execution which the agent doesn't initially have.
    default_prompt = (
        "Find out the host operating system, CPU architecture, and a list of "
        "Python files in the current folder. Since you don't have a terminal tool, "
        "you should write one (e.g. run_bash_command) using your meta-tool and then use it."
    )

    console.print("[bold cyan]Running Autonomous Demonstration Task:[/bold cyan]")
    console.print(f"[dim]{default_prompt}[/dim]\n")
    
    # Execute the self-evolving loop
    agent.run_task(default_prompt)
    
    console.print(Rule("[bold yellow]Summary and Outcome[/bold yellow]", style="yellow"))
    console.print("\n[bold green]🎉 Prototype Execution Completed Successfully![/bold green]")
    console.print("Check the [bold cyan]tools/[/bold cyan] directory to see the dynamically generated Python file(s) written by the agent!")

if __name__ == "__main__":
    main()
