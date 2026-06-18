#!/usr/bin/env python3
import os
import sys
import textwrap
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Initialize the Console for Rich terminal formatting
console = Console()

# -----------------------------------------------------------------------------
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# -----------------------------------------------------------------------------

class RubricEvaluation(BaseModel):
    empathy_score: int = Field(
        ..., 
        description="Score from 1 (poor/indifferent) to 5 (extremely empathetic and warm)."
    )
    empathy_justification: str = Field(
        ..., 
        description="Justification for the empathy score with specific evidence from the agent response."
    )
    accuracy_score: int = Field(
        ..., 
        description="Score from 1 (inaccurate/hallucinated) to 5 (fully accurate and fact-based)."
    )
    accuracy_justification: str = Field(
        ..., 
        description="Justification for the accuracy score."
    )
    actionability_score: int = Field(
        ..., 
        description="Score from 1 (unhelpful/vague) to 5 (provides clear, immediate next steps)."
    )
    actionability_justification: str = Field(
        ..., 
        description="Justification for the actionability score."
    )
    overall_verdict: str = Field(
        ..., 
        description="A concise summary verdict of the agent's response performance."
    )


class GoldenAnswerEvaluation(BaseModel):
    closeness_score: int = Field(
        ..., 
        description="Score from 0 to 100 representing how close the candidate answer is in meaning, technical correctness, and completeness to the Golden Answer."
    )
    detailed_justification: str = Field(
        ..., 
        description="Detailed explanation of how close the candidate answer is to the Golden Answer, noting what matched and what was different or incorrect."
    )

# -----------------------------------------------------------------------------
# SAMPLE DATA FOR DEMONSTRATIONS
# -----------------------------------------------------------------------------

# Task 1: Fixed Rubrics Evaluation (Customer Support Representative)
CUSTOMER_INQUIRY = (
    "I've been charged twice for my subscription this month ($15.00 each)! "
    "This is ridiculous, I want a refund immediately, and my account cancelled!"
)

RESPONSE_A_EXCELLENT = (
    "Hello! I am so sorry for the double charge and the frustration this has caused. "
    "I completely understand why you'd want this resolved right away. I have already "
    "initiated a refund of $15.00 back to your card, which should appear in 3-5 business days. "
    "I've verified that your account is currently still active. If you would still like me to "
    "cancel your subscription, please reply directly to this message and I will process the "
    "cancellation immediately so you aren't charged again. Please let me know if there is anything "
    "else I can do to help!"
)

RESPONSE_B_POOR = (
    "Hi, we sometimes have billing glitches. Your card was probably charged twice by mistake. "
    "It should refund automatically. Or you can contact your bank. If you want to cancel, "
    "go to your settings and click cancel. Thanks."
)


# Task 2: Golden Answer Comparison (Database Backup Retention)
SOURCE_CONTEXT = (
    "Customer asks: How do I configure backup retention policies in the DB cluster?"
)

GOLDEN_ANSWER = (
    "To configure backup retention in your DB cluster, navigate to the Cluster Console, "
    "select your cluster, and go to 'Backup & Restore'. Modify the 'Retention Period' "
    "(supported values are from 1 to 35 days). You can also enable 'Continuous Backups' "
    "for point-in-time recovery down to the second. Changes take effect during the next "
    "maintenance window unless 'Apply Immediately' is checked."
)

CANDIDATE_A_GOOD = (
    "Go to the Cluster Console, select your cluster, and click on 'Backup & Restore'. "
    "You can change the 'Retention Period' to any value between 1 and 35 days. If you want "
    "point-in-time recovery down to the second, make sure to enable 'Continuous Backups'. "
    "Note that edits are applied in the next maintenance window unless you select 'Apply Immediately'."
)

CANDIDATE_B_BAD = (
    "You can configure backup retention by calling `gcloud databases set-retention`. "
    "It supports up to 90 days of retention. Backups are stored in multi-region buckets by "
    "default. You can configure this through the command line or console settings."
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS FOR RENDERING
# -----------------------------------------------------------------------------

def score_to_color_1_5(score: int) -> str:
    if score >= 4:
        return "green"
    elif score >= 3:
        return "yellow"
    else:
        return "red"

def score_to_color_100(score: int) -> str:
    if score >= 80:
        return "green"
    elif score >= 50:
        return "yellow"
    else:
        return "red"

def render_model_io(prompt: str, response_json: str):
    """Renders the prompt and response in a beautiful chat box style per the design guide."""
    # Input Block
    input_elements = [
        Text.assemble(("USER: ", "bold blue"), (textwrap.fill(prompt, width=82, subsequent_indent="      "), "blue"))
    ]
    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    # Output Block
    wrapped_response = textwrap.fill(response_json, width=82, subsequent_indent="           ")
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

def print_rubrics():
    """Renders the evaluation rubrics nicely in the terminal before running the LLM."""
    console.print("  [bold cyan]-- Rubrics ----------------------------------------------------[/bold cyan]")
    console.print("  [bold]1. Empathy & Tone:[/bold] Does the agent acknowledge the customer's frustration")
    console.print("     with empathy and maintain a professional, helpful tone?")
    console.print("  [bold]2. Accuracy & Correctness:[/bold] Does the agent provide accurate information,")
    console.print("     or do they make unsupported claims/guesses?")
    console.print("  [bold]3. Actionability:[/bold] Does the agent provide clear, actionable next steps")
    console.print("     or resolution to the customer's issue?")
    console.print("  [bold cyan]---------------------------------------------------------------[/bold cyan]")
    console.print()

# -----------------------------------------------------------------------------
# MAIN DEMO PIPELINE
# -----------------------------------------------------------------------------

def main():
    # Setup client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
        
    client = genai.Client()
    model_name = "gemini-2.5-flash"

    # 1. Opening Header
    console.print(
        Panel.fit(
            "[bold yellow]LLM-as-a-Judge Demonstration[/bold yellow]\n"
            "[dim]A practical implementation of evaluating outputs using Gemini 2.5 Flash.[/dim]\n"
            "[dim]Scenarios: Fixed Rubrics Evaluation & Golden Answer Subjective Comparison[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    # =========================================================================
    # TASK 1: FIXED RUBRICS EVALUATION
    # =========================================================================
    console.print(Rule("[bold]Scenario 1: Fixed Rubric Evaluation (Customer Support)[/bold]", style="white"))
    console.print()
    
    console.print("[bold cyan]Customer Inquiry:[/bold cyan]")
    console.print(f"  [dim]\"\"\"{CUSTOMER_INQUIRY}\"\"\"[/dim]\n")
    
    console.print("[bold cyan]Response A (Expected Excellent):[/bold cyan]")
    console.print(f"  [green]\"\"\"{RESPONSE_A_EXCELLENT}\"\"\"[/green]\n")
    
    console.print("[bold magenta]Response B (Expected Poor):[/bold magenta]")
    console.print(f"  [red]\"\"\"{RESPONSE_B_POOR}\"\"\"[/red]\n")

    # Evaluate Response A
    console.print("[bold yellow]Evaluating Response A against rubrics...[/bold yellow]")
    print_rubrics()
    prompt_a = f"""
You are an expert Quality Assurance Judge for Customer Support.
Evaluate the following customer support representative's response to a customer inquiry based on the fixed rubrics provided.

[Customer Inquiry]
{CUSTOMER_INQUIRY}

[Agent Response to Evaluate]
{RESPONSE_A_EXCELLENT}

Your task is to assign a score from 1 to 5 for each of the following rubrics:
1. Empathy & Tone: Does the agent acknowledge the customer's frustration with empathy and maintain a professional, helpful tone?
2. Accuracy & Correctness: Does the agent provide accurate information, or do they make unsupported claims/guesses?
3. Actionability: Does the agent provide clear, actionable next steps or resolution to the customer's issue?

For each score, provide a brief but concrete justification based on specific evidence in the response.
Finally, provide an overall verdict summarizing the performance.
"""
    
    response_a = client.models.generate_content(
        model=model_name,
        contents=prompt_a,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RubricEvaluation,
            temperature=0.0,
        ),
    )
    
    render_model_io(prompt_a, response_a.text)
    eval_a_data: RubricEvaluation = response_a.parsed

    # Evaluate Response B
    console.print("[bold yellow]Evaluating Response B against rubrics...[/bold yellow]")
    print_rubrics()
    prompt_b = f"""
You are an expert Quality Assurance Judge for Customer Support.
Evaluate the following customer support representative's response to a customer inquiry based on the fixed rubrics provided.

[Customer Inquiry]
{CUSTOMER_INQUIRY}

[Agent Response to Evaluate]
{RESPONSE_B_POOR}

Your task is to assign a score from 1 to 5 for each of the following rubrics:
1. Empathy & Tone: Does the agent acknowledge the customer's frustration with empathy and maintain a professional, helpful tone?
2. Accuracy & Correctness: Does the agent provide accurate information, or do they make unsupported claims/guesses?
3. Actionability: Does the agent provide clear, actionable next steps or resolution to the customer's issue?

For each score, provide a brief but concrete justification based on specific evidence in the response.
Finally, provide an overall verdict summarizing the performance.
"""
    
    response_b = client.models.generate_content(
        model=model_name,
        contents=prompt_b,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RubricEvaluation,
            temperature=0.0,
        ),
    )
    
    render_model_io(prompt_b, response_b.text)
    eval_b_data: RubricEvaluation = response_b.parsed

    # Print Comparison Table
    table_rubric = Table(title="Scenario 1 Comparison (Fixed Rubrics, 1-5)", show_lines=True)
    table_rubric.add_column("Rubric / Metric", style="bold", min_width=24)
    table_rubric.add_column("Response A (Excellent) Score", justify="center")
    table_rubric.add_column("Response A Justification", style="dim")
    table_rubric.add_column("Response B (Poor) Score", justify="center")
    table_rubric.add_column("Response B Justification", style="dim")
    
    table_rubric.add_row(
        "Empathy & Tone",
        f"[{score_to_color_1_5(eval_a_data.empathy_score)}]{eval_a_data.empathy_score}/5[/{score_to_color_1_5(eval_a_data.empathy_score)}]",
        eval_a_data.empathy_justification,
        f"[{score_to_color_1_5(eval_b_data.empathy_score)}]{eval_b_data.empathy_score}/5[/{score_to_color_1_5(eval_b_data.empathy_score)}]",
        eval_b_data.empathy_justification,
    )
    table_rubric.add_row(
        "Accuracy & Correctness",
        f"[{score_to_color_1_5(eval_a_data.accuracy_score)}]{eval_a_data.accuracy_score}/5[/{score_to_color_1_5(eval_a_data.accuracy_score)}]",
        eval_a_data.accuracy_justification,
        f"[{score_to_color_1_5(eval_b_data.accuracy_score)}]{eval_b_data.accuracy_score}/5[/{score_to_color_1_5(eval_b_data.accuracy_score)}]",
        eval_b_data.accuracy_justification,
    )
    table_rubric.add_row(
        "Actionability",
        f"[{score_to_color_1_5(eval_a_data.actionability_score)}]{eval_a_data.actionability_score}/5[/{score_to_color_1_5(eval_a_data.actionability_score)}]",
        eval_a_data.actionability_justification,
        f"[{score_to_color_1_5(eval_b_data.actionability_score)}]{eval_b_data.actionability_score}/5[/{score_to_color_1_5(eval_b_data.actionability_score)}]",
        eval_b_data.actionability_justification,
    )
    
    table_rubric.add_section()
    table_rubric.add_row(
        "Overall Verdict",
        "[bold green]PASS[/bold green]",
        eval_a_data.overall_verdict,
        "[bold red]FAIL[/bold red]",
        eval_b_data.overall_verdict,
    )
    
    console.print(table_rubric)
    console.print()

    # =========================================================================
    # TASK 2: GOLDEN ANSWER COMPARISON
    # =========================================================================
    console.print(Rule("[bold]Scenario 2: Comparison against Golden Answer (DB Config)[/bold]", style="white"))
    console.print()
    
    console.print("[bold cyan]Source Context:[/bold cyan]")
    console.print(f"  [dim]{SOURCE_CONTEXT}[/dim]\n")
    
    console.print("[bold yellow]Golden Answer (Reference):[/bold yellow]")
    console.print(f"  [green]\"\"\"{GOLDEN_ANSWER}\"\"\"[/green]\n")
    
    console.print("[bold cyan]Candidate A (Expected Good):[/bold cyan]")
    console.print(f"  [cyan]\"\"\"{CANDIDATE_A_GOOD}\"\"\"[/cyan]\n")
    
    console.print("[bold magenta]Candidate B (Expected Bad):[/bold magenta]")
    console.print(f"  [magenta]\"\"\"{CANDIDATE_B_BAD}\"\"\"[/magenta]\n")

    # Evaluate Candidate A
    console.print("[bold yellow]Evaluating Candidate A against Golden Answer...[/bold yellow]")
    prompt_cand_a = f"""
You are an expert technical documentation judge.
Your task is to compare a generated candidate answer against a hand-crafted "Golden Answer" which represents the standard of excellence.
Evaluate how close the candidate answer is in meaning, technical correctness, and completeness to the Golden Answer.

[Source Context / Prompt]
{SOURCE_CONTEXT}

[Golden Answer (Standard of Excellence)]
{GOLDEN_ANSWER}

[Candidate Answer to Evaluate]
{CANDIDATE_A_GOOD}

Evaluate:
1. Closeness Score (0-100): How close is the Candidate Answer to the Golden Answer? (100 means they are completely identical in meaning, correctness, and completeness).
2. Detailed justification: Provide a thorough explanation of what matches, what is different, and what might be incorrect in the candidate answer compared to the Golden Answer.
"""
    
    response_cand_a = client.models.generate_content(
        model=model_name,
        contents=prompt_cand_a,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GoldenAnswerEvaluation,
            temperature=0.0,
        ),
    )
    
    render_model_io(prompt_cand_a, response_cand_a.text)
    eval_cand_a_data: GoldenAnswerEvaluation = response_cand_a.parsed

    # Evaluate Candidate B
    console.print("[bold yellow]Evaluating Candidate B against Golden Answer...[/bold yellow]")
    prompt_cand_b = f"""
You are an expert technical documentation judge.
Your task is to compare a generated candidate answer against a hand-crafted "Golden Answer" which represents the standard of excellence.
Evaluate how close the candidate answer is in meaning, technical correctness, and completeness to the Golden Answer.

[Source Context / Prompt]
{SOURCE_CONTEXT}

[Golden Answer (Standard of Excellence)]
{GOLDEN_ANSWER}

[Candidate Answer to Evaluate]
{CANDIDATE_B_BAD}

Evaluate:
1. Closeness Score (0-100): How close is the Candidate Answer to the Golden Answer? (100 means they are completely identical in meaning, correctness, and completeness).
2. Detailed justification: Provide a thorough explanation of what matches, what is different, and what might be incorrect in the candidate answer compared to the Golden Answer.
"""
    
    response_cand_b = client.models.generate_content(
        model=model_name,
        contents=prompt_cand_b,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GoldenAnswerEvaluation,
            temperature=0.0,
        ),
    )
    
    render_model_io(prompt_cand_b, response_cand_b.text)
    eval_cand_b_data: GoldenAnswerEvaluation = response_cand_b.parsed

    # Print Golden Answer Comparative Results Table
    table_golden = Table(title="Scenario 2 Comparison (Subjective Golden Score, 0-100)", show_lines=True)
    table_golden.add_column("Evaluation Metric", style="bold", min_width=24)
    table_golden.add_column("Candidate A (Good)", justify="center")
    table_golden.add_column("Candidate B (Bad)", justify="center")
    
    table_golden.add_row(
        "Closeness Score",
        f"[{score_to_color_100(eval_cand_a_data.closeness_score)}]{eval_cand_a_data.closeness_score}%[/{score_to_color_100(eval_cand_a_data.closeness_score)}]",
        f"[{score_to_color_100(eval_cand_b_data.closeness_score)}]{eval_cand_b_data.closeness_score}%[/{score_to_color_100(eval_cand_b_data.closeness_score)}]"
    )
    
    table_golden.add_section()
    table_golden.add_row(
        "Closeness Justification",
        f"[green]{eval_cand_a_data.detailed_justification}[/green]",
        f"[red]{eval_cand_b_data.detailed_justification}[/red]"
    )
    
    console.print(table_golden)
    console.print()

if __name__ == "__main__":
    main()
