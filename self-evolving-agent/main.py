import sys
import time
from agent import SelfEvolvingAgent, console
from rich.panel import Panel
from rich.rule import Rule

def run_one_time_flow(prompt: str):
    console.print(Rule("[bold cyan]Running Flow 1: One-Time Script Execution[/bold cyan]", style="cyan"))
    console.print()
    
    start_time = time.time()
    try:
        agent = SelfEvolvingAgent(mode="one_time")
        agent.run_task(prompt)
        elapsed = time.time() - start_time
        # Count turns in history
        # History has: User prompt (1), Assistant (model content), Tool call response, Assistant final answer.
        # Each model response with a function_call is a step.
        steps = sum(1 for item in agent.history if item.role in ("model", "assistant") and any(p.function_call for p in item.parts))
        return {
            "success": True,
            "elapsed": elapsed,
            "steps": steps,
            "history_length": len(agent.history)
        }
    except Exception as e:
        console.print(f"[bold red]Error running One-Time flow:[/bold red] {str(e)}")
        return {"success": False, "error": str(e)}

def run_long_term_flow(prompt: str):
    console.print(Rule("[bold magenta]Running Flow 2: Long-Term Tool Registration[/bold magenta]", style="magenta"))
    console.print()
    
    start_time = time.time()
    try:
        agent = SelfEvolvingAgent(mode="long_term")
        agent.run_task(prompt)
        elapsed = time.time() - start_time
        steps = sum(1 for item in agent.history if item.role in ("model", "assistant") and any(p.function_call for p in item.parts))
        return {
            "success": True,
            "elapsed": elapsed,
            "steps": steps,
            "history_length": len(agent.history)
        }
    except Exception as e:
        console.print(f"[bold red]Error running Long-Term flow:[/bold red] {str(e)}")
        return {"success": False, "error": str(e)}

def main():
    # Print opening header panel using rich styling
    console.print(
        Panel.fit(
            "[bold yellow]🧬 Gemini 2.5 Self-Evolving Agent Prototype[/bold yellow]\n"
            "[dim]An autonomous agent demonstrating two distinct ways to execute code and expand capability.[/dim]\n"
            "[dim]Powered by Gemini 2.5 Flash & the new google-genai SDK[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # The challenge task: Requires terminal/shell execution which the agent doesn't initially have.
    default_prompt = (
        "Find out the host operating system, CPU architecture, and a list of "
        "Python files in the current folder."
    )

    console.print("[bold cyan]Demonstration Task:[/bold cyan]")
    console.print(f"[dim]{default_prompt}[/dim]\n")
    
    # Run Flow 1: One-Time Script Execution
    one_time_res = run_one_time_flow(default_prompt)
    console.print()
    
    # Clean up any generated tools directory files before the long term flow so it's a fresh run
    import os
    if os.path.exists("tools"):
        for f in os.listdir("tools"):
            if f != "__init__.py":
                try:
                    os.remove(os.path.join("tools", f))
                except:
                    pass
                        
    # Run Flow 2: Long-Term Tool Registration
    long_term_res = run_long_term_flow(default_prompt)
    console.print()
    
    # Print summary of both flows
    console.print(Rule("[bold yellow]Execution Summary[/bold yellow]", style="yellow"))
    console.print()
    
    if one_time_res.get("success"):
        console.print(f"[bold cyan]Flow 1 (One-Time Script) Success![/bold cyan]")
        console.print(f"  Time Taken: [bold cyan]{one_time_res['elapsed']:.2f}s[/bold cyan] | Steps: [bold cyan]{one_time_res['steps']}[/bold cyan]")
    else:
        console.print(f"[bold red]Flow 1 Failed:[/bold red] {one_time_res.get('error')}")
        
    if long_term_res.get("success"):
        console.print(f"[bold magenta]Flow 2 (Long-Term Tool) Success![/bold magenta]")
        console.print(f"  Time Taken: [bold magenta]{long_term_res['elapsed']:.2f}s[/bold magenta] | Steps: [bold magenta]{long_term_res['steps']}[/bold magenta]")
        console.print("  Check the [bold cyan]tools/[/bold cyan] directory to see the dynamically generated Python file(s) written by the agent!")
    else:
        console.print(f"[bold red]Flow 2 Failed:[/bold red] {long_term_res.get('error')}")
        
    console.print()
    console.print("[bold green]🎉 Both flows completed successfully![/bold green]")

if __name__ == "__main__":
    main()
