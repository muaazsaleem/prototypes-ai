import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Load environment variables
load_dotenv()

console = Console()

# ---------------------------------------------------------------------------
# API CLIENT INITIALIZATION
# ---------------------------------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client(api_key=api_key)
else:
    # If no API key is set, we print a gentle reminder and use simulated mode.
    # This keeps the prototype runnable out-of-the-box for everyone.
    pass

# ---------------------------------------------------------------------------
# AGENT SYSTEM PROMPTS & BUSINESS POLICIES
# ---------------------------------------------------------------------------
REFUND_SYSTEM_PROMPT = (
    "You are a Refund Agent. Your sole responsibility is processing refunds.\n"
    "CRITICAL COMPANY POLICY:\n"
    "You are STRICTLY FORBIDDEN from processing any refund for items damaged in transit until the Shipping Agent "
    "has officially confirmed the damage status of the shipment.\n"
    "If you do not see a message from the Shipping Agent confirming the transit damage, you must NOT "
    "authorize the refund under any circumstance. Instead, you MUST immediately hand off the ticket to the "
    "Shipping Agent using the `handoff_to_shipping` tool to request confirmation.\n"
    "Keep your explanation concise and execute the handoff."
)

SHIPPING_SYSTEM_PROMPT = (
    "You are a Shipping Agent. Your responsibility is to inspect shipments and verify damage.\n"
    "CRITICAL COMPANY POLICY:\n"
    "You are STRICTLY FORBIDDEN from performing any transit damage inspection or confirmation until the Refund Agent "
    "has officially authorized the refund ticket in our ticketing database.\n"
    "If you do not see a message from the Refund Agent stating that they have officially authorized the refund ticket, "
    "you must NOT confirm any damage under any circumstance. Instead, you MUST immediately hand off the ticket "
    "back to the Refund Agent using the `handoff_to_refund` tool to get the ticket authorized first.\n"
    "Keep your explanation concise and execute the handoff."
)

# ---------------------------------------------------------------------------
# TOOL DEFINITIONS (Passed to Gemini as Function Declarations)
# ---------------------------------------------------------------------------
def handoff_to_shipping(reason: str) -> str:
    """Handoff the support ticket to the shipping agent to verify transit damage status.
    
    Args:
        reason: The reason for handing off to shipping.
    """
    return f"Handoff to shipping initiated. Reason: {reason}"

def handoff_to_refund(reason: str) -> str:
    """Handoff the support ticket back to the refund agent for refund ticket authorization.
    
    Args:
        reason: The reason for handing off to refund.
    """
    return f"Handoff to refund initiated. Reason: {reason}"

# ---------------------------------------------------------------------------
# DISPLAY HELPERS
# ---------------------------------------------------------------------------
def display_input_box(agent_name: str, conversation_history: list):
    input_elements = []
    for msg in conversation_history:
        role = msg["role_label"]
        content = msg.get("content", "")
        
        if role == "User":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "Refund Agent":
            label_style = "bold cyan"
            content_style = "cyan"
        elif role == "Shipping Agent":
            label_style = "bold magenta"
            content_style = "magenta"
        elif role == "Handoff Tool":
            label_style = "bold yellow"
            content_style = "yellow"
        else:
            label_style = "dim"
            content_style = "dim"
            
        text_line = Text.assemble((f"{role.upper()}: ", label_style), (content, content_style))
        input_elements.append(text_line)
        input_elements.append(Rule(style="bright_black"))
        
    if input_elements:
        input_elements.pop() # Remove trailing rule
        
    console.print(
        Panel(
            Group(*input_elements),
            title=f"[bold bright_black]Input History for {agent_name}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

def display_output_box(agent_name: str, response_text: str):
    if response_text is None:
        response_text = ""
    color = "cyan" if agent_name == "Refund Agent" else "magenta"
    response_content = Text.assemble(
        (f"{agent_name.upper()}: ", f"bold {color}"),
        (response_text, "italic")
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

# ---------------------------------------------------------------------------
# SIMULATOR MODE FALLBACK
# ---------------------------------------------------------------------------
def query_agent_simulated(agent_name: str, conversation_history: list):
    """Simulates Gemini's reasoning based on strict system instructions.
    
    This matches exactly how gemini-2.5-flash reacts when given the strict circular business rules.
    """
    time.sleep(1.2) # Realism delay
    
    class MockFunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

    class MockResponse:
        def __init__(self, text, function_calls):
            self.text = text
            self.function_calls = function_calls

    if agent_name == "Refund Agent":
        # Check if shipping has confirmed damage
        shipping_confirmed = any(
            "confirm" in m.get("content", "").lower() and "damage" in m.get("content", "").lower() and m.get("role_label") == "Shipping Agent"
            for m in conversation_history
        )
        
        if not shipping_confirmed:
            reason = "We cannot process a refund until the Shipping Agent confirms the transit damage status."
            response_text = (
                "I understand you are requesting a refund for your transit-damaged item. However, according to company policy, "
                "I am strictly forbidden from authorizing any refund until our shipping department confirms the transit damage. "
                "I must hand this ticket over to the Shipping Agent to verify the shipment status."
            )
            return MockResponse(response_text, [MockFunctionCall("handoff_to_shipping", {"reason": reason})])
            
    elif agent_name == "Shipping Agent":
        # Check if refund has authorized ticket
        refund_authorized = any(
            "authorize" in m.get("content", "").lower() and "refund" in m.get("content", "").lower() and m.get("role_label") == "Refund Agent"
            for m in conversation_history
        )
        
        if not refund_authorized:
            reason = "We cannot inspect transit damage until the Refund Agent has officially authorized the refund ticket."
            response_text = (
                "Hello. I see you are asking for transit damage verification. However, our shipping department is strictly forbidden "
                "from performing any inspections until the refund department officially authorizes the refund ticket. "
                "I am handing this back to the Refund Agent so they can authorize the ticket first."
            )
            return MockResponse(response_text, [MockFunctionCall("handoff_to_refund", {"reason": reason})])
            
    return MockResponse("Let me see what else I can do.", [])

# ---------------------------------------------------------------------------
# CORE QUERY ROUTER
# ---------------------------------------------------------------------------
def query_llm_or_sim(agent_name: str, system_instruction: str, conversation_history: list, tools: list):
    if not client:
        return query_agent_simulated(agent_name, conversation_history)
        
    # Build text transcript of conversation history to pass to Gemini
    transcript = "Here is the ongoing customer ticket and agent handoff history:\n\n"
    for msg in conversation_history:
        role = msg["role_label"]
        content = msg["content"]
        transcript += f"[{role}]: {content}\n"
    transcript += f"\nYou are the {agent_name}. Based on the rules above, what is your next action?"
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=transcript,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        return response
    except Exception as e:
        console.print(f"[bold red]Gemini API Exception:[/bold red] {e}")
        console.print("[yellow]Falling back to Simulator mode to maintain demo continuity.[/yellow]\n")
        return query_agent_simulated(agent_name, conversation_history)

# ---------------------------------------------------------------------------
# AGENT LOOPS (Inner loops within agent functions)
# ---------------------------------------------------------------------------
step_count = 0
max_steps = 8

def run_refund_agent(conversation_history: list) -> str:
    global step_count
    console.print(Rule("[bold cyan]Refund Agent (Refund Loop Started)[/bold cyan]", style="cyan"))
    console.print()
    
    while True:
        step_count += 1
        if step_count > max_steps:
            return "exit"
            
        console.print(f"[bold cyan]-- Refund Agent Turn #{step_count} --------------------------------------[/bold cyan]")
        display_input_box("Refund Agent", conversation_history)
        
        # Get decision from Gemini or Simulator
        response = query_llm_or_sim(
            agent_name="Refund Agent",
            system_instruction=REFUND_SYSTEM_PROMPT,
            conversation_history=conversation_history,
            tools=[handoff_to_shipping]
        )
        
        # Safely extract response text or default if only function calls were returned
        response_text = response.text
        if not response_text:
            if response.function_calls:
                fc = response.function_calls[0]
                response_text = f"[Initiating handoff to shipping agent... Reason: {fc.args.get('reason', 'Prerequisite check')}]"
            else:
                response_text = "[No message content returned]"
                
        display_output_box("Refund Agent", response_text)
        
        # Record response
        conversation_history.append({
            "role": "model",
            "role_label": "Refund Agent",
            "content": response_text
        })
        
        # Process tool/function calls if any
        if response.function_calls:
            fc = response.function_calls[0]
            if fc.name == "handoff_to_shipping":
                reason = fc.args.get("reason", "No reason provided.")
                console.print(f"  [bold yellow][Tool Invoked][/bold yellow] [italic]handoff_to_shipping(reason='{reason}')[/italic]")
                
                # Append tool execution to history so the next agent is aware of it
                conversation_history.append({
                    "role": "tool",
                    "role_label": "Handoff Tool",
                    "content": f"Successfully handed off to shipping. Action item: Verify damage status. Reason: {reason}"
                })
                
                # Hand over to shipping. Break the inner refund loop and return "shipping" to the outer loop.
                console.print("[bold yellow]Breaking Refund Loop to Hand Off control to Shipping Agent.[/bold yellow]\n")
                return "shipping"
                
        # If no tool was called (e.g., standard message or error), exit to avoid hanging
        console.print("[yellow]No handoff tool invoked by Refund Agent. Ending loop.[/yellow]\n")
        return "exit"

def run_shipping_agent(conversation_history: list) -> str:
    global step_count
    console.print(Rule("[bold magenta]Shipping Agent (Shipping Loop Started)[/bold magenta]", style="magenta"))
    console.print()
    
    while True:
        step_count += 1
        if step_count > max_steps:
            return "exit"
            
        console.print(f"[bold magenta]-- Shipping Agent Turn #{step_count} ------------------------------------[/bold magenta]")
        display_input_box("Shipping Agent", conversation_history)
        
        # Get decision
        response = query_llm_or_sim(
            agent_name="Shipping Agent",
            system_instruction=SHIPPING_SYSTEM_PROMPT,
            conversation_history=conversation_history,
            tools=[handoff_to_refund]
        )
        
        # Safely extract response text or default if only function calls were returned
        response_text = response.text
        if not response_text:
            if response.function_calls:
                fc = response.function_calls[0]
                response_text = f"[Initiating handoff to refund agent... Reason: {fc.args.get('reason', 'Prerequisite check')}]"
            else:
                response_text = "[No message content returned]"
                
        display_output_box("Shipping Agent", response_text)
        
        # Record response
        conversation_history.append({
            "role": "model",
            "role_label": "Shipping Agent",
            "content": response_text
        })
        
        # Process tool/function calls
        if response.function_calls:
            fc = response.function_calls[0]
            if fc.name == "handoff_to_refund":
                reason = fc.args.get("reason", "No reason provided.")
                console.print(f"  [bold yellow][Tool Invoked][/bold yellow] [italic]handoff_to_refund(reason='{reason}')[/italic]")
                
                # Append tool execution
                conversation_history.append({
                    "role": "tool",
                    "role_label": "Handoff Tool",
                    "content": f"Successfully handed off to refund. Action item: Authorize refund ticket. Reason: {reason}"
                })
                
                # Hand over to refund. Break the inner shipping loop and return "refund" to the outer loop.
                console.print("[bold yellow]Breaking Shipping Loop to Hand Off control to Refund Agent.[/bold yellow]\n")
                return "refund"
                
        # If no tool was called, exit
        console.print("[yellow]No handoff tool invoked by Shipping Agent. Ending loop.[/yellow]\n")
        return "exit"

# ---------------------------------------------------------------------------
# MAIN EXECUTION ROUTINE
# ---------------------------------------------------------------------------
def main():
    global step_count
    
    # 1. Title Header
    console.print(
        Panel.fit(
            "[bold red]🔄 Agent Hand-off Deadlock Simulation[/bold red]\n"
            "[dim]Demonstrating infinite loop issues in multi-agent routing due to circular policy dependencies.[/dim]\n"
            f"[dim]Run Mode: {'GENUINE GEMINI API (gemini-2.5-flash)' if client else 'SIMULATED LLM REASONING'}[/dim]",
            border_style="red",
        )
    )
    console.print()

    # 2. Setup initial state
    current_agent = "refund"
    conversation_history = [
        {
            "role": "user",
            "role_label": "User",
            "content": "I want a refund for my order #12345. It arrived with a broken screen, so it was clearly damaged in transit!"
        }
    ]

    console.print("[bold yellow]Initial Support Ticket Created:[/bold yellow]")
    console.print(f"  [dim]User:[/dim] [italic]\"{conversation_history[0]['content']}\"[/italic]\n")
    
    console.print("[bold cyan]Agent Hand-off Rules:[/bold cyan]")
    console.print("  1. [bold]Refund Agent[/bold] cannot issue refund without [bold]Shipping Agent[/bold] confirming transit damage status.")
    console.print("  2. [bold]Shipping Agent[/bold] cannot inspect/confirm damage without [bold]Refund Agent[/bold] authorizing refund ticket first.")
    console.print("  [dim]Resulting Expectation: Infinite cycle (Deadlock).[/dim]\n")
    
    input("Press Enter to begin the simulation...")
    console.print()

    # 3. The Outer While Loop
    while current_agent != "exit" and step_count < max_steps:
        if current_agent == "refund":
            current_agent = run_refund_agent(conversation_history)
        elif current_agent == "shipping":
            current_agent = run_shipping_agent(conversation_history)

    # 4. Final Verdict and Summary
    console.print()
    console.print(Rule("[bold yellow]Simulation Complete: Overall Summary[/bold yellow]", style="yellow"))
    console.print()
    
    if step_count >= max_steps:
        verdict = "[bold red]🚨 SYSTEM DEADLOCK DETECTED! 🚨[/bold red]"
        explanation = (
            f"The agents entered an infinite handoff cycle, exceeding the maximum allowed steps of {max_steps}.\n\n"
            "• [bold cyan]The Refund Agent[/bold cyan] couldn't proceed because the shipping damage status was unverified.\n"
            "• [bold magenta]The Shipping Agent[/bold magenta] couldn't proceed because the refund ticket was unauthorized.\n\n"
            "Neither agent could fulfill their prerequisite, causing them to repeatedly call their handoff tools in a "
            "circular dependency, resulting in a classic system deadlock (infinite routing loop)."
        )
    else:
        verdict = "[bold green]✅ Simulation Finished Safely.[/bold green]"
        explanation = "The simulation finished before reaching the step limit, and no deadlock occurred."

    console.print(Panel(
        Group(
            Text.from_markup(f"Verdict: {verdict}\n"),
            Text.from_markup(explanation),
            Text.from_markup(
                "\n[bold green]How to solve Agent Deadlocks?[/bold green]\n"
                "1. [bold]Orchestrator Routing[/bold]: Instead of direct handoffs, an orchestrator tracks visit history and breaks loops.\n"
                "2. [bold]Prerequisite Relaxation[/bold]: Redesign state requirements (e.g., Shipping Agent inspects first independently of the ticket).\n"
                "3. [bold]Cycle Detection[/bold]: Implement middleware that monitors the agent execution stack and raises an exception when a cycle is detected."
            )
        ),
        title="[bold yellow]Analysis Report[/bold yellow]",
        border_style="yellow",
        padding=(1, 2)
    ))

if __name__ == "__main__":
    main()
