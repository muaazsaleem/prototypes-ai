#!/usr/bin/env python3
"""
Gemini Evaluation Suite Prototype
Demonstrating automated LLM evaluations using the modern google-genai SDK.
"""

import sys
import os
import textwrap
from enum import Enum
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# Rich terminal styling imports
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize Rich Console
console = Console()

# Verify API Key availability
if "GEMINI_API_KEY" not in os.environ:
    console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set.")
    console.print("Please export GEMINI_API_KEY before running this script.")
    sys.path_to_env_file = ".env"
    sys.exit(1)

# Initialize google-genai client
client = genai.Client()
EVAL_MODEL = "gemini-2.5-flash"


# =====================================================================
# SCHEMA DEFINITIONS (Pydantic Models)
# =====================================================================

# --- 1. Classification ---
class Category(str, Enum):
    BILLING = "BILLING"
    TECH_SUPPORT = "TECH_SUPPORT"
    SALES = "SALES"

class IntentClassification(BaseModel):
    category: Category = Field(description="The classified category of the user query.")
    reasoning: str = Field(description="Brief reasoning for why this category was selected.")


# --- 2. Rubric-Based LLM-as-a-Judge ---
class RubricScore(BaseModel):
    score: int = Field(description="The graded score from 1 to 5 based on the provided rubric.")
    reasoning: str = Field(description="Detailed reasoning explaining why this score was given, citing specific parts of the response.")


# --- 3. Golden-Output Comparison ---
class GoldenComparison(BaseModel):
    is_equivalent: bool = Field(description="True if the actual response accurately captures all key factual points in the golden output. False otherwise.")
    missing_points: list[str] = Field(description="List of key factual points or constraints present in the golden output but missing in the candidate response.")
    reasoning: str = Field(description="Detailed explanation of the semantic comparison and factual overlap.")


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def accuracy_bar(correct: int, total: int, width: int = 20) -> Text:
    """Renders a colorful text progress bar representing accuracy."""
    pct = correct / total if total > 0 else 0
    filled = round(pct * width)
    bar = "X" * filled + "." * (width - filled)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    return Text(f"{bar}  {correct}/{total}  ({int(pct*100)}%)", style=color)


def print_chat_box(title_prefix: str, messages: list[dict]):
    """Helper to display model input/output prompts matching the 'terminal-output-style' spec."""
    input_elements = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        
        if role == "system":
            label_style = "dim"
            content_style = "dim"
        elif role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "assistant":
            label_style = "bold green"
            content_style = "green"
        elif role == "judge":
            label_style = "bold magenta"
            content_style = "magenta"
        else:
            label_style = "bold yellow"
            content_style = "yellow"
            
        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        input_elements.append(Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style)))
        input_elements.append(Rule(style="bright_black"))
        
    if input_elements:
        input_elements.pop()  # Remove trailing rule
        
    console.print(
        Panel(
            Group(*input_elements),
            title=f"[bold bright_black]{title_prefix}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


# =====================================================================
# EVALUATION SCENARIOS
# =====================================================================

def run_classification_evals() -> tuple[int, int]:
    """Runs classification evaluation on fixed output schemas."""
    console.print(Rule("[bold]Classification Evaluation (Fixed Output Schema)[/bold]", style="white"))
    console.print()
    console.print("[bold cyan]-- Running Classification Checks --------------------------------------[/bold cyan]")
    
    test_cases = [
        {
            "query": "I was charged twice for my subscription this month. Can I get a refund?",
            "expected": Category.BILLING
        },
        {
            "query": "The mobile app crashes on startup on my iOS 17 device when opening settings.",
            "expected": Category.TECH_SUPPORT
        },
        {
            "query": "Is there a custom enterprise tier with custom SLAs for teams of 100+ members?",
            "expected": Category.SALES
        }
    ]
    
    passed_count = 0
    total_count = len(test_cases)
    
    # Per-item result table
    result_table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    result_table.add_column("Query Snippet", min_width=30)
    result_table.add_column("Expected", justify="center")
    result_table.add_column("Actual", justify="center")
    result_table.add_column("Result", justify="center")
    result_table.add_column("Reasoning", style="dim", min_width=30)
    
    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        expected = test["expected"]
        
        prompt = f"Classify the following customer support ticket into one of the allowed categories:\nTicket: {query}"
        
        # Invoke Gemini with structured output constraint
        response = client.models.generate_content(
            model=EVAL_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=IntentClassification,
                temperature=0.0,  # Deterministic output
            )
        )
        
        # Parse output Pydantic model
        result = response.parsed
        is_correct = result.category == expected
        passed = "[green]o[/green]" if is_correct else "[red]o[/red]"
        
        # Live run progress dots
        console.print(f"  Classification Test #{i:02d}: {passed} [dim]Done[/dim]", end="   ", highlight=False)
        if i % 4 == 0 or i == total_count:
            console.print()
            
        verdict = "[bold green]correct[/bold green]" if is_correct else "[bold red]wrong[/bold red]"
        if is_correct:
            passed_count += 1
            
        snippet = query[:35] + "..." if len(query) > 35 else query
        result_table.add_row(snippet, expected.value, result.category.value, verdict, result.reasoning)
        
    console.print()
    console.print(result_table)
    console.print()
    return passed_count, total_count


def run_rubric_evals() -> tuple[int, int]:
    """Runs Rubric-based evaluation using LLM-as-a-Judge."""
    console.print(Rule("[bold]Rubric-Based LLM-as-a-Judge Evaluation[/bold]", style="white"))
    console.print()
    console.print("[bold magenta]-- Grading Agent Responses with Rubric ---------------------------------[/bold magenta]")
    
    rubric_text = """
    Evaluate the response's 'Tone and Politeness' on a 1-5 scale:
    5 - Excellent: Exceptionally polite, empathetic, professional, and directly addresses the issue with a warm, supportive tone.
    4 - Good: Polite and professional. Addresses the issue clearly and shows reasonable empathy.
    3 - Neutral: Direct and professional, but completely lacks warmth or active empathy.
    2 - Poor: Brief, cold, or slightly dismissive. Lacks basic politeness.
    1 - Unacceptable: Rude, hostile, or completely inappropriate.
    """
    
    test_cases = [
        {
            "query": "I lost my login details, please help!",
            "response": "I am so sorry to hear that you're locked out! Don't worry, we'll get you back in. Please click the 'Forgot Password' link on the login screen or let me know if you'd like me to send a password reset link to your registered email address.",
            "description": "Warm & empathetic response",
            "min_expected_score": 4
        },
        {
            "query": "I lost my login details, please help!",
            "response": "Go to the login screen and click forgot password. It will send a link.",
            "description": "Cold/abrupt response",
            "min_expected_score": 3  # Neutral
        },
        {
            "query": "I lost my login details, please help!",
            "response": "We can't do anything about you losing your password. Figure it out.",
            "description": "Rude/hostile response",
            "min_expected_score": 1  # Unacceptable/Poor
        }
    ]
    
    passed_count = 0
    total_count = len(test_cases)
    
    # Per-item result table
    result_table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    result_table.add_column("Case", style="bold")
    result_table.add_column("Assigned Score", justify="center")
    result_table.add_column("Evaluation", justify="center")
    result_table.add_column("Reasoning Summary", style="dim", min_width=45)
    
    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        response_text = test["response"]
        desc = test["description"]
        min_score = test["min_expected_score"]
        
        judge_prompt = f"""
        You are an expert quality assurance judge evaluating customer support responses.
        
        RUBRIC:
        {rubric_text}
        
        INPUT DETAILS:
        User Query: {query}
        Assistant Response: {response_text}
        
        Grade the assistant response according to the Rubric.
        """
        
        # Invoke Judge LLM
        response = client.models.generate_content(
            model=EVAL_MODEL,
            contents=judge_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RubricScore,
                temperature=0.0,
            )
        )
        
        eval_result = response.parsed
        score = eval_result.score
        
        # Let's say it passes if score matches expectations (just to create a binary pass/fail for summary)
        # Warm should score >= 4, Cold should score 2 or 3, Rude should score <= 2
        is_pass = False
        if min_score == 4 and score >= 4:
            is_pass = True
        elif min_score == 3 and score in (2, 3):
            is_pass = True
        elif min_score == 1 and score <= 2:
            is_pass = True
            
        passed = "[green]o[/green]" if is_pass else "[yellow]o[/yellow]"
        console.print(f"  Rubric Judge Test #{i:02d}: {passed} [dim]{desc} graded {score}/5[/dim]", end="   ", highlight=False)
        if i % 4 == 0 or i == total_count:
            console.print()
            
        verdict = "[bold green]PASS[/bold green]" if is_pass else "[bold yellow]NEUTRAL[/bold yellow]"
        if is_pass:
            passed_count += 1
            
        # We can occasionally display the actual evaluation in structured chat box style
        if i == 1:
            console.print()
            print_chat_box(
                f"Rubric Case #{i}: Model Input & Judge Response",
                [
                    {"role": "user", "content": f"Query: {query}\nResponse: {response_text}"},
                    {"role": "judge", "content": f"Score: {score}/5\nReasoning: {eval_result.reasoning}"}
                ]
            )
            
        reasoning_snippet = eval_result.reasoning[:70] + "..." if len(eval_result.reasoning) > 70 else eval_result.reasoning
        result_table.add_row(desc, f"[bold]{score}/5[/bold]", verdict, reasoning_snippet)
        
    console.print()
    console.print(result_table)
    console.print()
    return passed_count, total_count


def run_golden_evals() -> tuple[int, int]:
    """Runs golden-output based comparison using LLM-as-a-Judge."""
    console.print(Rule("[bold]Golden-Output Based Evaluation (Factual Equivalency Judge)[/bold]", style="white"))
    console.print()
    console.print("[bold cyan]-- Comparing Candidate Responses against Ground Truth -----------------[/bold cyan]")
    
    test_cases = [
        {
            "query": "What is your refund policy?",
            "golden": "We offer a full refund within 30 days of purchase. No refunds are given after 30 days have elapsed.",
            "response": "Our policy allows you to request all of your money back if you contact us within the first 30 days after buying. Once those 30 days have passed, we unfortunately cannot process any refunds.",
            "expected_match": True,
            "description": "Factually equivalent, different phrasing"
        },
        {
            "query": "What is your refund policy?",
            "golden": "We offer a full refund within 30 days of purchase. No refunds are given after 30 days have elapsed.",
            "response": "You can get a complete refund if you don't like the product, just email support.",
            "expected_match": False,
            "description": "Missing the 30-day constraint!"
        }
    ]
    
    passed_count = 0
    total_count = len(test_cases)
    
    # Per-item result table
    result_table = Table(show_header=True, header_style="bold", padding=(0, 2), show_edge=False)
    result_table.add_column("Scenario Description", style="bold")
    result_table.add_column("Golden Equivalent?", justify="center")
    result_table.add_column("Verdict", justify="center")
    result_table.add_column("Missing Points Highlighted by Judge", style="red", min_width=30)
    
    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        golden = test["golden"]
        response_text = test["response"]
        expected = test["expected_match"]
        desc = test["description"]
        
        judge_prompt = f"""
        You are a meticulous ground-truth compliance judge.
        Compare the Candidate Response with the Golden Output (ground truth) for the user query below.
        Determine if they are semantically equivalent and capture all core factual details and constraints.
        
        User Query: {query}
        Golden Output (Ground Truth): {golden}
        Candidate Response to Evaluate: {response_text}
        """
        
        # Invoke Golden Comparison Judge
        response = client.models.generate_content(
            model=EVAL_MODEL,
            contents=judge_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GoldenComparison,
                temperature=0.0,
            )
        )
        
        eval_result = response.parsed
        is_equivalent = eval_result.is_equivalent
        
        # Test passes if the judge output matches the expected result
        test_passed = (is_equivalent == expected)
        
        passed_dot = "[green]o[/green]" if test_passed else "[red]o[/red]"
        console.print(f"  Golden Comparison Test #{i:02d}: {passed_dot} [dim]{desc}[/dim]", end="   ", highlight=False)
        if i % 4 == 0 or i == total_count:
            console.print()
            
        verdict = "[bold green]correct[/bold green]" if test_passed else "[bold red]wrong[/bold red]"
        if test_passed:
            passed_count += 1
            
        # Display the second test case in detail so the user sees the missing points detection in action!
        if i == 2:
            console.print()
            print_chat_box(
                f"Golden Case #{i}: Factual Incompleteness Detection",
                [
                    {"role": "system", "content": f"GOLDEN ANSWER: {golden}"},
                    {"role": "user", "content": f"CANDIDATE RESPONSE: {response_text}"},
                    {"role": "judge", "content": f"Is Equivalent: {is_equivalent}\nMissing Points: {eval_result.missing_points}\nReasoning: {eval_result.reasoning}"}
                ]
            )
            
        missing_str = ", ".join(eval_result.missing_points) if eval_result.missing_points else "None"
        is_equiv_str = "[green]Yes[/green]" if is_equivalent else "[red]No[/red]"
        result_table.add_row(desc, is_equiv_str, verdict, missing_str)
        
    console.print()
    console.print(result_table)
    console.print()
    return passed_count, total_count


# =====================================================================
# MAIN EXECUTION FLOW
# =====================================================================

def main():
    # Opening header
    console.print(
        Panel.fit(
            "[bold yellow]Gemini LLM Evaluation Suite Prototype[/bold yellow]\n"
            "[dim]Demonstrating automated evaluations of different types using the new google-genai SDK.[/dim]\n"
            "[dim]Includes: Classification schema validation, Rubric scoring, and Golden-output comparison.[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    
    # 1. Run Classification
    class_correct, class_total = run_classification_evals()
    
    # 2. Run Rubric
    rubric_correct, rubric_total = run_rubric_evals()
    
    # 3. Run Golden Comparison
    golden_correct, golden_total = run_golden_evals()
    
    # 4. Final Summary Table
    console.print(Rule("[bold yellow]Overall Summary[/bold yellow]", style="yellow"))
    console.print()
    
    total_correct = class_correct + rubric_correct + golden_correct
    total_runs = class_total + rubric_total + golden_total
    
    summary_table = Table(title="Evaluation Metrics Summary", show_lines=True)
    summary_table.add_column("Evaluation Type", style="bold", min_width=30)
    summary_table.add_column("Passed", justify="center")
    summary_table.add_column("Accuracy Visualizer Bar", justify="left")
    summary_table.add_column("Status", justify="center")
    
    # Add Rows
    summary_table.add_row(
        "Classification (Fixed Output)",
        f"{class_correct}/{class_total}",
        accuracy_bar(class_correct, class_total, 25),
        "[green]PASS[/green]" if class_correct == class_total else "[yellow]PARTIAL[/yellow]"
    )
    summary_table.add_row(
        "Rubric Based LLM-as-Judge",
        f"{rubric_correct}/{rubric_total}",
        accuracy_bar(rubric_correct, rubric_total, 25),
        "[green]PASS[/green]" if rubric_correct == rubric_total else "[yellow]PARTIAL[/yellow]"
    )
    summary_table.add_row(
        "Golden-Output Comparison",
        f"{golden_correct}/{golden_total}",
        accuracy_bar(golden_correct, golden_total, 25),
        "[green]PASS[/green]" if golden_correct == golden_total else "[yellow]PARTIAL[/yellow]"
    )
    
    summary_table.add_section()
    
    # Totals Row
    summary_table.add_row(
        "[bold]TOTAL COMBINED METRICS[/bold]",
        f"[bold]{total_correct}/{total_runs}[/bold]",
        accuracy_bar(total_correct, total_runs, 25),
        "[bold green]ALL PASS[/bold green]" if total_correct == total_runs else "[bold yellow]PARTIAL PASS[/bold yellow]"
    )
    
    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    main()
