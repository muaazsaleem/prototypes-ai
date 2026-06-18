import os
import time
import json
import uuid
import contextlib
from typing import Dict, Any, List
from dotenv import load_dotenv

# Import rich elements for professional console output
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
import textwrap

# Load environment variables
load_dotenv()

# Initialize Rich Console
console = Console()

# --- PRE-CONFIGURED MOCK DATA AND PROFILES ---
USER_PROFILES = [
    {
        "id": "1",
        "user_id": "usr_free_456",
        "name": "Bob (Free Tier)",
        "metadata": {
            "plan": "free",
            "department": "Marketing",
            "region": "US-East",
            "max_daily_budget_usd": "0.10"
        }
    },
    {
        "id": "2",
        "user_id": "usr_premium_789",
        "name": "Alice (Premium Tier)",
        "metadata": {
            "plan": "premium",
            "department": "R&D",
            "region": "EU-West",
            "max_daily_budget_usd": "2.00"
        }
    },
    {
        "id": "3",
        "user_id": "usr_enterprise_101",
        "name": "Charlie (Enterprise Tier)",
        "metadata": {
            "plan": "enterprise",
            "department": "Global Data Science",
            "region": "AP-South",
            "max_daily_budget_usd": "50.00"
        }
    }
]

SUGGESTED_PROMPTS = [
    {
        "id": "1",
        "topic": "Explain Quantum Computing speedup",
        "query": "Why are quantum computers faster than classical computers? Keep it brief."
    },
    {
        "id": "2",
        "topic": "What is LLM Fine-Tuning?",
        "query": "How does LLM fine-tuning differ from Retrieval-Augmented Generation (RAG)?"
    },
    {
        "id": "3",
        "topic": "Explain Fusion Energy challenges",
        "query": "What are the main engineering obstacles to commercial nuclear fusion power?"
    }
]

# Standard pricing for gemini-2.5-flash (USD per token)
# Input: $0.075 / 1,000,000 tokens = $0.000000075
# Output: $0.30 / 1,000,000 tokens = $0.00000030
GEMINI_INPUT_COST_PER_TOKEN = 0.075 / 1_000_000
GEMINI_OUTPUT_COST_PER_TOKEN = 0.30 / 1_000_000

# Mock DB articles for RAG simulation
KNOWLEDGE_BASE = {
    "quantum": (
        "Quantum computing speedup arises from two core principles: superposition and entanglement. "
        "Superposition allows a quantum bit (qubit) to represent a 0, a 1, or both simultaneously, "
        "meaning a quantum system can explore an exponential number of states at once. "
        "Entanglement links qubits such that the state of one instantly influences another. "
        "Together with quantum interference, they allow quantum algorithms (like Shor's or Grover's) "
        "to amplify correct pathways and cancel incorrect ones, solving specific complex problems "
        "exponentially faster than classical brute force."
    ),
    "fine-tuning": (
        "Retrieval-Augmented Generation (RAG) and Fine-Tuning serve different purposes. "
        "RAG is like an 'open-book' exam: it dynamically fetches fresh, external documents and feeds "
        "them to the LLM's prompt context to answer specific questions, ensuring high factual accuracy "
        "without changing the model's weights. Fine-Tuning is like 'internalizing' knowledge: "
        "it is a process of training the model on specific datasets to permanently alter its weights, "
        "primarily used for adapting tone, style, output formatting, or teaching domain-specific behavior "
        "rather than injecting dynamic real-time information."
    ),
    "fusion": (
        "Commercializing nuclear fusion faces immense engineering obstacles. First is plasma confinement: "
        "magnetic confinement devices (Tokamaks) must keep hydrogen isotope plasmas heated to over "
        "150 million degrees Celsius (ten times hotter than the sun's core) stable and dense enough for "
        "sustained periods. Second is materials science: the reactor walls must survive extreme neutron "
        "bombardment, which degrades standard materials. Third is tritium breeding: tritium, a key fuel "
        "isotope, must be bred inside the reactor itself. Lastly, the net-energy gain (Q factor) "
        "must be scaled from momentary physical gains to continuous, cost-effective power generation."
    )
}

# --- INITIALIZATION AND CONDITIONAL IMPORTS ---
HAS_LANGFUSE = False
HAS_GEMINI = False

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Check if keys are placeholders rather than actual secrets
if GOOGLE_API_KEY == "your_google_api_key_here":
    GOOGLE_API_KEY = None
if LANGFUSE_PUBLIC_KEY == "pk-lf-...":
    LANGFUSE_PUBLIC_KEY = None

# Attempt Langfuse import and activation
if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        from langfuse import observe, propagate_attributes, Langfuse
        # Ensure client can initialize
        lf_test = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST
        )
        HAS_LANGFUSE = True
    except Exception as e:
        console.print(f"[yellow]Warning: Could not initialize real Langfuse client: {e}[/yellow]")
        HAS_LANGFUSE = False

# Attempt Gemini import and activation
if GOOGLE_API_KEY:
    try:
        from google import genai
        client_test = genai.Client(api_key=GOOGLE_API_KEY)
        HAS_GEMINI = True
    except Exception as e:
        console.print(f"[yellow]Warning: Could not initialize Google GenAI client: {e}[/yellow]")
        HAS_GEMINI = False

# If credentials aren't set, we define lightweight dummy equivalents so python executes without errors
if not HAS_LANGFUSE:
    # Mocking modern decorators & context managers
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    @contextlib.contextmanager
    def propagate_attributes(**kwargs):
        yield

# Setup standard auto-instrumentation for Gemini through Langfuse
if HAS_LANGFUSE and HAS_GEMINI:
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        GoogleGenAIInstrumentor().instrument()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not activate auto-instrumentation: {e}[/yellow]")


# --- SIMULATION FALLBACKS ---

def simulate_refine_query(raw_query: str) -> Dict[str, str]:
    time.sleep(0.3)
    q = raw_query.lower()
    if "quantum" in q:
        return {"search_term": "quantum computer speedup superposition entanglement", "topic": "quantum"}
    elif "fine-tuning" in q or "rag" in q:
        return {"search_term": "difference rag fine-tuning model adaptation", "topic": "fine-tuning"}
    else:
        return {"search_term": "nuclear fusion tokamak engineering plasma", "topic": "fusion"}

def simulate_synthesis(raw_query: str, context: str) -> str:
    time.sleep(0.6)
    return (
        f"Based on the provided documentation:\n\n"
        f"Yes, Gemini 2.5 Flash can synthesize this information rapidly. "
        f"Referring specifically to: '{context[:110]}...'.\n\n"
        f"In summary, we achieve LLM observability by routing traces and attributing costs "
        f"directly to the subscription plan of the query. This ensures proper billing."
    )


# --- MULTI-STEP WORKFLOW PIPELINE ---

@observe(name="Query Refinement", as_type="span")
def refine_query_step(raw_query: str) -> Dict[str, str]:
    """
    Step 1: Analyzes the user's raw query and extracts a refined search term and topic key.
    """
    if HAS_GEMINI:
        try:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            prompt = (
                "You are an assistant. Extract the core subject from the user query. "
                "Output JSON with two keys: 'search_term' (concise keywords) and "
                "'topic' (must be exactly one of: 'quantum', 'fine-tuning', or 'fusion').\n"
                f"Query: '{raw_query}'"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text_out = response.text
            # Simple parsing fallback
            try:
                clean_text = text_out.strip().replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_text)
            except:
                topic = "quantum" if "quantum" in text_out.lower() else "fine-tuning" if "fine" in text_out.lower() else "fusion"
                result = {"search_term": text_out[:60].strip(), "topic": topic}
            
            # Return parsed dictionary along with usage metadata
            usage = response.usage_metadata
            result["_prompt_tokens"] = usage.prompt_token_count if usage else 30
            result["_completion_tokens"] = usage.candidates_token_count if usage else 15
            return result
        except Exception as e:
            console.print(f"[red]Error in real Gemini refine step: {e}[/red]")
    
    # Fallback to simulation
    res = simulate_refine_query(raw_query)
    res["_prompt_tokens"] = 32
    res["_completion_tokens"] = 12
    return res


@observe(name="Database Retrieval", as_type="retriever")
def retrieve_db_context_step(topic_key: str) -> str:
    """
    Step 2: Fetches reference articles from our local mock database.
    This demonstrates non-LLM span tracking in Langfuse (as a Retriever).
    """
    time.sleep(0.2)  # Simulate small database I/O latency
    return KNOWLEDGE_BASE.get(topic_key, KNOWLEDGE_BASE["quantum"])


@observe(name="Response Synthesis", as_type="span")
def synthesize_response_step(raw_query: str, db_context: str) -> Dict[str, Any]:
    """
    Step 3: Performs final synthesis using the original query and retrieved context.
    """
    if HAS_GEMINI:
        try:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            prompt = (
                f"You are an expert engineer. Using this article context:\n"
                f"'{db_context}'\n\n"
                f"Briefly answer this user question: '{raw_query}'"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            
            usage = response.usage_metadata
            return {
                "text": response.text,
                "_prompt_tokens": usage.prompt_token_count if usage else 220,
                "_completion_tokens": usage.candidates_token_count if usage else 80
            }
        except Exception as e:
            console.print(f"[red]Error in real Gemini synthesis step: {e}[/red]")
            
    # Fallback to simulation
    text_out = simulate_synthesis(raw_query, db_context)
    return {
        "text": text_out,
        "_prompt_tokens": 210,
        "_completion_tokens": 75
    }


@observe(name="LLM Observability Pipeline")
def run_observability_pipeline(user_profile: Dict[str, Any], raw_query: str) -> Dict[str, Any]:
    """
    Orchestrates the query-refinement, retrieval, and synthesis pipeline.
    Using `propagate_attributes`, we ensure all downstream spans, retrievals, and LLM 
    calls automatically inherit cost attribution fields (user_id, plan tags, and custom metadata).
    """
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    plan = user_profile["metadata"]["plan"]
    
    # Use propagation context manager to tag all child traces and auto-instrumented generations
    with propagate_attributes(
        user_id=user_profile["user_id"],
        tags=["demo-prototype", f"plan-{plan}"],
        metadata={
            "environment": "prototype-cli",
            "subscription_tier": plan,
            "department": user_profile["metadata"]["department"],
            "region": user_profile["metadata"]["region"],
            "max_budget_usd": user_profile["metadata"]["max_daily_budget_usd"]
        }
    ):
        # Step 1: Query refinement
        refinement_start = time.time()
        refined_data = refine_query_step(raw_query)
        refinement_latency = time.time() - refinement_start
        
        # Step 2: Database retrieval (Non-LLM Span)
        retrieval_start = time.time()
        topic = refined_data.get("topic", "quantum")
        context = retrieve_db_context_step(topic)
        retrieval_latency = time.time() - retrieval_start
        
        # Step 3: Synthesis
        synthesis_start = time.time()
        synthesis_data = synthesize_response_step(raw_query, context)
        synthesis_latency = time.time() - synthesis_start
        
        total_latency = time.time() - start_time
        
        # Calculate tokens and costs
        p_tok1 = refined_data.get("_prompt_tokens", 0)
        c_tok1 = refined_data.get("_completion_tokens", 0)
        p_tok3 = synthesis_data.get("_prompt_tokens", 0)
        c_tok3 = synthesis_data.get("_completion_tokens", 0)
        
        total_prompt_tokens = p_tok1 + p_tok3
        total_completion_tokens = c_tok1 + c_tok3
        total_tokens = total_prompt_tokens + total_completion_tokens
        
        cost_input = total_prompt_tokens * GEMINI_INPUT_COST_PER_TOKEN
        cost_output = total_completion_tokens * GEMINI_OUTPUT_COST_PER_TOKEN
        total_cost_usd = cost_input + cost_output
        
        return {
            "trace_id": trace_id,
            "raw_query": raw_query,
            "user_profile": user_profile,
            "metrics": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": total_cost_usd,
                "latency": total_latency
            },
            "steps": [
                {
                    "name": "Query Refinement",
                    "type": "generation",
                    "model": "gemini-2.5-flash",
                    "input": f"Raw Query: '{raw_query}'",
                    "output": f"Search term: '{refined_data['search_term']}' | Topic: '{topic}'",
                    "prompt_tokens": p_tok1,
                    "completion_tokens": c_tok1,
                    "latency": refinement_latency
                },
                {
                    "name": "Database Retrieval",
                    "type": "retriever",
                    "input": f"Search term: '{refined_data['search_term']}'",
                    "output": f"Fetched {len(context)} characters from DB about topic '{topic}'",
                    "latency": retrieval_latency
                },
                {
                    "name": "Response Synthesis",
                    "type": "generation",
                    "model": "gemini-2.5-flash",
                    "input": f"Answer '{raw_query}' using context: '{context[:60]}...'",
                    "output": synthesis_data["text"],
                    "prompt_tokens": p_tok3,
                    "completion_tokens": c_tok3,
                    "latency": synthesis_latency
                }
            ]
        }


# --- DISPLAY PIPELINE RUNS (RICH) ---

def display_workflow_trace(result: Dict[str, Any], live_mode: bool):
    """
    Renders an elegant dashboard visualization in the terminal using Rich.
    """
    profile = result["user_profile"]
    metrics = result["metrics"]
    
    console.print()
    console.print(Rule("[bold cyan]LLM Observability - Active Workflow Trace[/bold cyan]", style="cyan"))
    console.print()
    
    # Trace Info Card
    status_tag = "[green]● ACTIVE COGNITIVE INSTRUMENTATION[/green]" if live_mode else "[yellow]● SIMULATED COGNITIVE TELEMETRY[/yellow]"
    console.print(
        Panel(
            f"[bold]Trace ID:[/bold] [magenta]{result['trace_id']}[/magenta]\n"
            f"[bold]Status:[/bold] {status_tag}\n"
            f"[bold]User Identification:[/bold] {profile['user_id']} ({profile['name']})\n"
            f"[bold]Associated Metadata:[/bold] [dim]Department: {profile['metadata']['department']} | Region: {profile['metadata']['region']}[/dim]\n"
            f"[bold]Associated Tags:[/bold] [yellow]demo-prototype[/yellow], [yellow]plan-{profile['metadata']['plan']}[/yellow]",
            title="[bold bright_black]Trace Metadata[/bold bright_black]",
            border_style="cyan"
        )
    )
    console.print()
    
    # Steps Timeline
    console.print("[bold cyan]-- Pipeline Spans & Generations -----------------------------[/bold cyan]")
    console.print()
    
    for i, step in enumerate(result["steps"]):
        latency_str = f"{step['latency']:.3f}s"
        
        if step.get("type") == "generation":
            tokens_info = f" | [dim]Prompt Tokens:[/dim] [blue]{step['prompt_tokens']}[/blue] | [dim]Completion Tokens:[/dim] [green]{step['completion_tokens']}[/green]"
            model_info = f"[bold magenta]{step['model']}[/bold magenta]"
            title_tag = f"Step {i+1}: {step['name']} ({model_info}) - {latency_str}{tokens_info}"
            
            msg_group = []
            wrapped_prompt = textwrap.fill(step["input"], width=82, subsequent_indent="  ")
            wrapped_resp = textwrap.fill(step["output"], width=82, subsequent_indent="  ")
            
            msg_group.append(Text.assemble(("PROMPT: ", "bold blue"), (wrapped_prompt, "blue")))
            msg_group.append(Rule(style="bright_black"))
            msg_group.append(Text.assemble(("RESPONSE: ", "bold green"), (wrapped_resp, "italic green")))
            
            console.print(
                Panel(
                    Group(*msg_group),
                    title=f"[bold bright_black]{title_tag}[/bold bright_black]",
                    border_style="bright_black",
                    padding=(1, 2)
                )
            )
        else:
            # Retriever or database lookup
            title_tag = f"Step {i+1}: {step['name']} - {latency_str}"
            span_content = (
                f"[bold yellow]INPUT SEARCH KEY:[/bold yellow] [dim]{step['input']}[/dim]\n"
                f"[bold yellow]RETRIEVAL SUMMARY:[/bold yellow] [italic]{step['output']}[/italic]"
            )
            console.print(
                Panel(
                    span_content,
                    title=f"[bold yellow]{title_tag}[/bold yellow]",
                    border_style="yellow",
                    padding=(1, 2)
                )
            )
        console.print()

    # Cost Attribution Table
    console.print(Rule("[bold yellow]LLM Cost Attribution Summary[/bold yellow]", style="yellow"))
    console.print()
    
    table = Table(show_lines=True)
    table.add_column("Attribute", style="bold cyan", min_width=20)
    table.add_column("Value", style="bold")
    
    table.add_row("User Identifier", f"[white]{profile['user_id']}[/white]")
    table.add_row("Assigned Plan / Tier", f"[white]{profile['metadata']['plan'].upper()}[/white]")
    table.add_row("Total Pipeline Latency", f"[white]{metrics['latency']:.3f} seconds[/white]")
    table.add_row("Total Prompt Tokens", f"[blue]{metrics['prompt_tokens']}[/blue]")
    table.add_row("Total Completion Tokens", f"[green]{metrics['completion_tokens']}[/green]")
    table.add_row("Total Token Consumption", f"[yellow]{metrics['total_tokens']}[/yellow]")
    
    # Cost styling
    cost_style = "green" if metrics['cost_usd'] < 0.0001 else "yellow" if metrics['cost_usd'] < 0.001 else "red"
    table.add_row(
        "Attributed Cost (USD)", 
        f"[{cost_style}]${metrics['cost_usd']:.8f}[/{cost_style}] ([dim]Gemini-2.5-Flash pricing[/dim])"
    )
    
    # Budget check
    max_budget = float(profile['metadata']['max_daily_budget_usd'])
    status = "[bold green]PASS (Under Budget)[/bold green]" if metrics['cost_usd'] < max_budget else "[bold red]BUDGET EXCEEDED[/bold red]"
    table.add_row("Daily Budget Cap", f"[dim]${max_budget:.2f}[/dim]")
    table.add_row("Budget Compliance Verdict", status)
    
    console.print(table)
    console.print()
    
    if live_mode:
        console.print(
            Panel(
                f"[bold green]✓ Trace successfully transmitted to Langfuse dashboard![/bold green]\n"
                f"To review cost attribution, sessions, and spans:\n"
                f"1. Open your Langfuse Dashboard: [bold blue]{LANGFUSE_HOST}[/bold blue]\n"
                f"2. Navigate to [bold]Traces[/bold] to see the active trace tree: [yellow]{result['trace_id']}[/yellow]\n"
                f"3. Go to the [bold]Users[/bold] tab to view aggregated metrics & costs for [bold magenta]{profile['user_id']}[/bold magenta].",
                border_style="green"
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]ℹ Running in Telemetry Simulation Mode[/bold yellow]\n"
                f"To export these spans & automatically attribute costs to your Langfuse workspace:\n"
                f"1. Create a free account at [bold blue]https://cloud.langfuse.com[/bold blue]\n"
                f"2. Add your credentials to the [bold].env[/bold] file in this directory:\n"
                f"   [dim]LANGFUSE_PUBLIC_KEY=pk-lf-...\n"
                f"   LANGFUSE_SECRET_KEY=sk-lf-...\n"
                f"   LANGFUSE_HOST=https://cloud.langfuse.com[/dim]\n"
                f"3. Provide your Google Gemini API Key: [dim]GOOGLE_API_KEY=your-api-key[/dim]\n"
                f"4. Re-run this script to stream trace records live!",
                border_style="yellow"
            )
        )
    console.print()


# --- CLI ENTRYPOINT ---

def main():
    # Welcome Header Panel
    console.print(
        Panel.fit(
            "[bold yellow]LLM Observability & Cost Attribution Prototype[/bold yellow]\n"
            "[dim]A super simple demonstration of Gemini 2.5 Flash tracing using Langfuse.[/dim]\n"
            "[dim]Features: Multi-step pipeline tracking, non-LLM custom spans, and cost mapping.[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    
    # Status Check
    status_items = []
    if HAS_GEMINI:
        status_items.append("[green]✓ Google Gemini SDK: Connected (Live Mode)[/green]")
    else:
        status_items.append("[yellow]⚠ Google Gemini SDK: No API Key found (Simulation Mode)[/yellow]")
        
    if HAS_LANGFUSE:
        status_items.append(f"[green]✓ Langfuse Tracing: Configured ({LANGFUSE_HOST})[/green]")
    else:
        status_items.append("[yellow]⚠ Langfuse Tracing: Not Configured (Local Mode)[/yellow]")
        
    console.print(Panel("\n".join(status_items), title="System Initialization Status", border_style="bright_black"))
    console.print()
    
    while True:
        console.print(Rule("[bold white]New Scenario Run[/bold white]", style="white"))
        console.print()
        
        # 1. Select User Profile
        console.print("[bold cyan]Choose a Mock User Profile (for Cost Attribution):[/bold cyan]")
        for idx, profile in enumerate(USER_PROFILES):
            console.print(f"  [{idx + 1}] [bold]{profile['name']}[/bold] | ID: [dim]{profile['user_id']}[/dim] | Dept: [dim]{profile['metadata']['department']}[/dim]")
        
        console.print()
        p_choice = console.input("[bold yellow]Enter Profile Choice (1-3) or 'q' to quit: [/bold yellow]").strip()
        if p_choice.lower() == 'q':
            break
        if p_choice not in ["1", "2", "3"]:
            console.print("[bold red]Invalid selection. defaulting to Alice (Premium).[/bold red]")
            selected_profile = USER_PROFILES[1]
        else:
            selected_profile = USER_PROFILES[int(p_choice) - 1]
            
        console.print()
        
        # 2. Select Topic/Query
        console.print("[bold cyan]Select an LLM Query Scenario:[/bold cyan]")
        for idx, item in enumerate(SUGGESTED_PROMPTS):
            console.print(f"  [{idx + 1}] [bold]{item['topic']}[/bold]\n      Query: [dim]'{item['query']}'[/dim]")
        console.print("  [4] Custom Query (Write your own!)")
        
        console.print()
        q_choice = console.input("[bold yellow]Enter Query Choice (1-4): [/bold yellow]").strip()
        
        if q_choice == "4":
            raw_query = console.input("\n[bold yellow]Enter your custom query: [/bold yellow]").strip()
            if not raw_query:
                raw_query = SUGGESTED_PROMPTS[0]["query"]
        elif q_choice in ["1", "2", "3"]:
            raw_query = SUGGESTED_PROMPTS[int(q_choice) - 1]["query"]
        else:
            console.print("[bold red]Invalid selection. defaulting to Query 1.[/bold red]")
            raw_query = SUGGESTED_PROMPTS[0]["query"]
            
        console.print()
        
        # 3. Execute Pipeline
        with console.status("[bold green]Executing LLM Observability Pipeline...", spinner="dots"):
            pipeline_result = run_observability_pipeline(selected_profile, raw_query)
            
        # 4. Render beautiful results
        is_live = HAS_GEMINI and HAS_LANGFUSE
        display_workflow_trace(pipeline_result, is_live)
        
        # Prompt to run again
        cont = console.input("[bold yellow]Would you like to run another scenario? (y/n): [/bold yellow]").strip().lower()
        if cont != 'y':
            break
            
    console.print()
    console.print("[bold green]Thank you for exploring LLM Observability and Cost Attribution![/bold green]")
    console.print()

if __name__ == "__main__":
    main()
