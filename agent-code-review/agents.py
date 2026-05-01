import json
import os
import textwrap

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from models import ReviewDecision, SpecialistReport

MODEL = "gemini-2.5-flash-preview-05-20"

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
console = Console()


def _call_gemini(prompt: str) -> dict:
    """Sends a prompt to Gemini and returns the response parsed as a dict.

    Forces JSON output via response_mime_type so the caller can safely parse
    response.text without guarding against markdown fences or prose.
    """
    # Display model input block
    input_elements = []
    # In this app, we only send a single user prompt
    role = "user"
    label_style = "bold blue"
    content_style = "blue"
    indent = " " * (len(role) + 2)
    wrapped = textwrap.fill(prompt, width=82, subsequent_indent=indent)
    input_elements.append(
        Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
    )

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    # Display model output block
    wrapped_response = textwrap.fill(
        response.text, width=82, subsequent_indent="           "
    )
    response_content = Text.assemble(
        ("ASSISTANT: ", "bold green"), (wrapped_response, "italic")
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

    # Parse the raw JSON response text into a Python dictionary
    return json.loads(response.text)


def run_style_agent(diff: str) -> SpecialistReport:
    """Runs the style specialist agent against a PR diff and returns its findings.

    Analyzes the diff for PEP8 compliance, naming, and general readability.
    Returns a SpecialistReport containing findings and a summary.
    """
    prompt = f"""You are a code style reviewer. Analyze the PR diff and identify style issues.
Focus on: naming conventions (PEP8 snake_case), formatting, readability, unnecessary verbosity,
comparison idioms (e.g. `is None` vs `== None`).

Return a JSON object with this exact structure:
{{
  "findings": [
    {{
      "line": <line number or null>,
      "severity": "<low|medium|high|critical>",
      "description": "<what the issue is>",
      "suggestion": "<how to fix it>"
    }}
  ],
  "summary": "<brief overall summary of style quality>"
}}

PR Diff:
{diff}"""

    data = _call_gemini(prompt)
    return SpecialistReport.from_dict("style", data)


def run_security_agent(diff: str) -> SpecialistReport:
    """Runs the security specialist agent against a PR diff and returns its findings.

    Analyzes the diff for security vulnerabilities like injections and secret exposure.
    Returns a SpecialistReport containing findings and a summary.
    """
    prompt = f"""You are a security-focused code reviewer. Analyze the PR diff for vulnerabilities.
Focus on: SQL injection, authentication flaws, insecure cryptography, secrets in code,
logging sensitive data, input validation, privilege escalation.

Return a JSON object with this exact structure:
{{
  "findings": [
    {{
      "line": <line number or null>,
      "severity": "<low|medium|high|critical>",
      "description": "<what the vulnerability is>",
      "suggestion": "<how to fix it>"
    }}
  ],
  "summary": "<brief overall summary of security posture>"
}}

PR Diff:
{diff}"""

    data = _call_gemini(prompt)
    return SpecialistReport.from_dict("security", data)


def run_logic_agent(diff: str) -> SpecialistReport:
    """Runs the logic specialist agent against a PR diff and returns its findings.

    Analyzes the diff for logical bugs, resource leaks, and edge cases.
    Returns a SpecialistReport containing findings and a summary.
    """
    prompt = f"""You are a logic and correctness reviewer. Analyze the PR diff for bugs.
Focus on: resource leaks (unclosed connections/files), incorrect conditions, missing error handling,
wrong assumptions, off-by-one errors, unreachable code.

Return a JSON object with this exact structure:
{{
  "findings": [
    {{
      "line": <line number or null>,
      "severity": "<low|medium|high|critical>",
      "description": "<what the logic issue is>",
      "suggestion": "<how to fix it>"
    }}
  ],
  "summary": "<brief overall summary of logic correctness>"
}}

PR Diff:
{diff}"""

    data = _call_gemini(prompt)
    return SpecialistReport.from_dict("logic", data)


def run_critic_agent(
    style_report: SpecialistReport,
    security_report: SpecialistReport,
    logic_report: SpecialistReport,
    memory_context: str,
    repo: str,
) -> ReviewDecision:
    """Consolidates findings from specialists and resolves conflicts.

    Uses past memory to ensure consistency and prioritizes security findings.
    Returns a consolidated ReviewDecision with a final verdict and key decisions.
    """
    prompt = f"""You are a senior engineer consolidating code review findings from three specialists.

MEMORY — past decisions for this repository. Do NOT contradict these:
{memory_context}

STYLE REVIEW:
{json.dumps(style_report.to_dict(), indent=2)}

SECURITY REVIEW:
{json.dumps(security_report.to_dict(), indent=2)}

LOGIC REVIEW:
{json.dumps(logic_report.to_dict(), indent=2)}

Your job:
1. Merge duplicate or overlapping findings into single entries
2. Resolve conflicts between specialists (security findings outrank style)
3. Maintain consistency with past decisions from memory
4. Assign a final verdict based on the highest severity issues

Return a JSON object with this exact structure:
{{
  "summary": "<overall review summary in 2-3 sentences>",
  "findings": [
    {{
      "line": <line number or null>,
      "severity": "<low|medium|high|critical>",
      "description": "<consolidated finding description>",
      "suggestion": "<clear actionable fix>"
    }}
  ],
  "verdict": "<approve|request_changes|comment>",
  "key_decisions": [
    "<an important standard or pattern enforced in this review>",
    ...
  ]
}}"""

    data = _call_gemini(prompt)
    # The repo context is needed for the ReviewDecision object but not the LLM
    return ReviewDecision.from_dict(repo, data)
