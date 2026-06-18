import os
import sys
import json
import ast
import textwrap
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import print as rprint

# Initialize Rich Console
console = Console()

class MemoryManager:
    """Manages the memory state using explicit ADD, UPSERT, and DELETE actions."""
    def __init__(self):
        self.memory = [] # List of tuples: (Subject, Relation, Object)

    def apply_actions(self, actions):
        """
        Applies a list of actions to the memory.
        - ADD: Appends a fact (allows multiple objects for same S/R).
        - UPSERT: Replaces existing S/R pair or adds if missing (single-value).
        - DELETE: Removes a specific fact.
        """
        changes = []
        if not isinstance(actions, list):
            return changes
            
        for action in actions:
            if not isinstance(action, dict):
                continue
                
            action_type = action.get("type")
            fact_str = action.get("fact")
            
            if not action_type or not fact_str:
                continue
            
            try:
                fact_tuple = ast.literal_eval(fact_str)
                if not (isinstance(fact_tuple, tuple) and len(fact_tuple) == 3):
                    continue
            except Exception:
                continue

            if action_type == "ADD":
                # ADD allows duplicates/multiple values (e.g., LIKES Pizza, LIKES Pasta)
                if fact_tuple not in self.memory:
                    self.memory.append(fact_tuple)
                    changes.append(fact_str)
            
            elif action_type == "UPSERT":
                # UPSERT replaces any existing fact with same S/R (e.g., LIVES_IN)
                updated = False
                for i, existing in enumerate(self.memory):
                    if existing[0] == fact_tuple[0] and existing[1] == fact_tuple[1]:
                        self.memory[i] = fact_tuple
                        changes.append(fact_str)
                        updated = True
                        break
                if not updated:
                    self.memory.append(fact_tuple)
                    changes.append(fact_str)

            elif action_type == "DELETE":
                # DELETE only if exact match found
                if fact_tuple in self.memory:
                    self.memory.remove(fact_tuple)
        
        return changes

    def get_as_strings(self):
        return [str(f) for f in self.memory]

def get_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set.")
        sys.exit(1)
    return genai.Client(api_key=api_key)

SYSTEM_PROMPT = """
You are a Memory Extraction Engine. Your task is to analyze a user's message and derive specific memory actions (ADD, UPSERT, DELETE).

CRITICAL RULES:
1. DO NOT try to "fix" or "reconcile" with the Current Memory. Simply extract actions based on the NEW user message.
2. ACTION TYPES:
   - ADD: Use this for facts that can have MULTIPLE values (e.g., LIKES, HAS_SKILL, INTERESTED_IN).
   - UPSERT: Use this for facts that should only have ONE value at a time (e.g., LIVES_IN, WORKS_AS, CURRENT_STATE). If the user mentions a new value for these, the system will replace the old one.
   - DELETE: Use this ONLY if the user explicitly asks to "forget", "remove", or "delete" a specific piece of information.
3. Use CRISP, UPPERCASE relations (e.g., LIVES_IN, WORKS_AS, LIKES).
4. Respond ONLY with a valid JSON object containing:
   - "actions": A list of action objects: {{"type": "ADD"|"UPSERT"|"DELETE", "fact": "('Subject', 'Relation', 'Object')"}}.
   - "new_facts": A brief list of the new specific details discovered in this turn.

Current Memory (For context ONLY, do not use to derive actions):
{current_memory}

New User Message:
{user_message}

Response (JSON):
"""


def get_memory_actions(client, current_memory, user_message):
    prompt = SYSTEM_PROMPT.format(
        current_memory=json.dumps(current_memory),
        user_message=user_message
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction="You are a memory management assistant. Output structured CRUD actions in JSON.",
                temperature=0.1,
                response_mime_type="application/json"
            ),
            contents=prompt
        )
    except Exception as e:
        console.print(f"[bold red]API Error:[/bold red] {e}")
        return [], []
    
    try:
        data = json.loads(response.text)
        actions = []
        new_facts = []

        if isinstance(data, list):
            actions = data
        elif isinstance(data, dict):
            # Check if it's the wrapper format
            if "actions" in data:
                raw_actions = data["actions"]
                if isinstance(raw_actions, list):
                    actions = raw_actions
                elif isinstance(raw_actions, dict):
                    actions = [raw_actions]
            # Check if the dictionary ITSELF is a single action
            elif "type" in data and "fact" in data:
                actions = [data]
            
            new_facts = data.get("new_facts", [])
        
        # Final pass: Ensure everything in actions is a dict
        final_actions = [a for a in actions if isinstance(a, dict)]
        return final_actions, new_facts

    except Exception as e:
        console.print(f"[bold red]Error parsing LLM response:[/bold red] {e}")
        console.print(f"[dim]Raw Response Body: {response.text}[/dim]")
        return [], []

def display_status(user_input, memory, new_facts, changes, actions):
    console.clear()
    
    console.print(Rule("[bold]Interaction History[/bold]", style="white"))
    console.print(f"\n[bold blue]> USER[/bold blue]")
    wrapped = textwrap.fill(user_input, width=88, subsequent_indent="  ")
    console.print(f"  {wrapped}")
    console.print()

    # Display raw actions for transparency
    if actions:
        action_lines = []
        for a in actions:
            a_type = a.get("type", "UNKNOWN")
            a_fact = a.get("fact", "()")
            color = "green" if a_type == "ADD" else "yellow" if a_type == "UPSERT" else "red"
            action_lines.append(f"[{color}]{a_type:7}[/{color}] {a_fact}")
        
        actions_panel = Panel(
            "\n".join(action_lines),
            title="[bold magenta]Memory Engine Actions[/bold magenta]",
            border_style="magenta",
            padding=(1, 2)
        )
        console.print(actions_panel)
        console.print()

    if new_facts and isinstance(new_facts, list):
        facts_text = "\n".join([f"• {f}" for f in new_facts])
        console.print(Panel(facts_text, title="[bold cyan]Key Extractions[/bold cyan]", border_style="cyan", padding=(1, 2)))
        console.print()

    table = Table(
        title="[bold yellow]Evolving Long-Term Memory[/bold yellow]",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )
    table.add_column("Subject", min_width=20)
    table.add_column("Relation", justify="center")
    table.add_column("Object")
    
    change_set = set(changes)
    
    for fact_tuple in memory:
        if not isinstance(fact_tuple, (tuple, list)) or len(fact_tuple) != 3:
            continue
            
        fact_str = str(fact_tuple)
        is_changed = fact_str in change_set
        
        style = "bold red" if is_changed else "white"
        rel_style = "bold red" if is_changed else "yellow"
        obj_style = "bold red" if is_changed else "green"

        table.add_row(
            Text(str(fact_tuple[0]), style=style),
            Text(str(fact_tuple[1]), style=rel_style),
            Text(str(fact_tuple[2]), style=obj_style)
        )
            
    console.print(table)
    console.print()
    if changes:
        console.print("[dim italic red]* Red entries indicate facts modified or added in this turn.[/dim italic red]")
    console.print(Rule(style="white"))

def main():
    client = get_client()
    manager = MemoryManager()
    
    console.print(
        Panel.fit(
            "[bold yellow]Evolving Memory Prototype (Action-Based)[/bold yellow]\n"
            "[dim]Memory evolution via explicit ADD, UPDATE, and DELETE actions.[/dim]\n"
            "[dim]Using Gemini 2.0 Flash[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    
    while True:
        try:
            user_input = console.input("[bold yellow]Chat > [/bold yellow]")
            if not user_input.strip():
                continue
                
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print(Rule("[bold yellow]Session Summary[/bold yellow]", style="yellow"))
                console.print("\n[bold green]Memory successfully evolved. Goodbye![/bold green]\n")
                break
            
            with console.status("[bold green]Calculating memory actions..."):
                actions, new_facts = get_memory_actions(client, manager.get_as_strings(), user_input)
                changes = manager.apply_actions(actions)
            
            display_status(user_input, manager.memory, new_facts, changes, actions)
            
        except KeyboardInterrupt:
            console.print("\n[bold red]Interrupted by user.[/bold red]")
            break
        except Exception:
            console.print_exception()

if __name__ == "__main__":
    main()
