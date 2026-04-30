#!/usr/bin/env python3
"""
Skill Executor: Multi-step AI Skill Decomposition with Schema Validation

Demonstrates how to decompose a complex task (GitHub repo health audit) into
typed skill steps, validate outputs at each boundary, and use a critic sub-step
to catch hallucinated data before it propagates.
"""

import json
import os
import re
import textwrap
import time
from dataclasses import dataclass, field

import jsonschema
from google import genai
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── Model Configuration ───────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 2

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ── Skill Data Types ──────────────────────────────────────────────────────────


@dataclass
class SkillStep:
    name: str
    description: str
    prompt_template: str
    output_schema: dict


@dataclass
class Skill:
    name: str
    description: str
    steps: list


@dataclass
class StepResult:
    step_name: str
    output: dict
    prompt_tokens: int
    output_tokens: int
    retries: int = 0
    critic_flagged: bool = False
    critic_issues: list = field(default_factory=list)


@dataclass
class SkillRun:
    repo_url: str
    step_results: list = field(default_factory=list)
    final_output: dict = field(default_factory=dict)
    monolithic_prompt_tokens: int = 0
    monolithic_output_tokens: int = 0


# ── Skill Definition: repo-health-audit ──────────────────────────────────────
#
# Each step has a narrow responsibility: one concern, one output schema.
# The executor passes step N's output as context into step N+1's prompt.

REPO_HEALTH_SKILL = Skill(
    name="repo-health-audit",
    description="Produces a structured engineering health report for a GitHub repository",
    steps=[
        SkillStep(
            name="clone_repo",
            description="Fetch repository metadata and assess overall structure",
            prompt_template="""Analyze the GitHub repository: {url}

Using your knowledge of this repository, return a JSON object:
{{
    "repo_name": "owner/repo",
    "language": "primary programming language",
    "stars": integer star count (approximate),
    "last_commit_age_days": integer days since last commit (approximate),
    "file_count_estimate": integer rough file count,
    "description": "one sentence description of what this repo does",
    "repo_type": "active|maintained|neglected|monorepo"
}}

Return ONLY the JSON. No markdown fences, no explanation.""",
            output_schema={
                "type": "object",
                "required": [
                    "repo_name",
                    "language",
                    "stars",
                    "last_commit_age_days",
                    "file_count_estimate",
                    "description",
                    "repo_type",
                ],
                "properties": {
                    "repo_name": {"type": "string"},
                    "language": {"type": "string"},
                    "stars": {"type": "integer"},
                    "last_commit_age_days": {"type": "integer"},
                    "file_count_estimate": {"type": "integer"},
                    "description": {"type": "string"},
                    "repo_type": {
                        "type": "string",
                        "enum": ["active", "maintained", "neglected", "monorepo"],
                    },
                },
            },
        ),
        SkillStep(
            name="static_analysis",
            description="Identify code complexity hotspots and maintainability issues",
            prompt_template="""Perform static analysis on: {repo_name}
Primary language: {language}
Description: {description}

Identify the top complexity hotspots and return a JSON object:
{{
    "hotspots": [
        {{"file": "relative/path/to/file.py", "issue": "brief complexity description", "severity": "high|medium|low"}}
    ],
    "avg_complexity_rating": "low|medium|high|very_high",
    "has_type_annotations": true or false,
    "code_duplication": "none|low|moderate|high",
    "maintainability_score": integer 0-100
}}

Return ONLY the JSON. No markdown fences, no explanation.""",
            output_schema={
                "type": "object",
                "required": [
                    "hotspots",
                    "avg_complexity_rating",
                    "has_type_annotations",
                    "code_duplication",
                    "maintainability_score",
                ],
                "properties": {
                    "hotspots": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["file", "issue", "severity"],
                            "properties": {
                                "file": {"type": "string"},
                                "issue": {"type": "string"},
                                "severity": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                },
                            },
                        },
                    },
                    "avg_complexity_rating": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "very_high"],
                    },
                    "has_type_annotations": {"type": "boolean"},
                    "code_duplication": {
                        "type": "string",
                        "enum": ["none", "low", "moderate", "high"],
                    },
                    "maintainability_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
            },
        ),
        SkillStep(
            name="dependency_check",
            description="Check dependency freshness and identify stale packages",
            prompt_template="""Check dependencies for: {repo_name}
Language: {language}

List the key dependencies of this project with their version information.
Return a JSON object:
{{
    "dependencies": [
        {{
            "name": "package name",
            "pinned_version": "version string currently used in the repo (e.g. 1.2.3)",
            "latest_version": "latest stable version available on PyPI/npm today",
            "months_behind": integer months since pinned version was released,
            "is_outdated": true or false,
            "has_known_cve": true or false
        }}
    ],
    "total_deps_count": integer,
    "outdated_count": integer,
    "risk_level": "low|medium|high|critical"
}}

IMPORTANT: Use real, accurate version numbers you are confident about.
Return ONLY the JSON. No markdown fences, no explanation.""",
            output_schema={
                "type": "object",
                "required": [
                    "dependencies",
                    "total_deps_count",
                    "outdated_count",
                    "risk_level",
                ],
                "properties": {
                    "dependencies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "name",
                                "pinned_version",
                                "latest_version",
                                "months_behind",
                                "is_outdated",
                                "has_known_cve",
                            ],
                            "properties": {
                                "name": {"type": "string"},
                                "pinned_version": {"type": "string"},
                                "latest_version": {"type": "string"},
                                "months_behind": {"type": "integer"},
                                "is_outdated": {"type": "boolean"},
                                "has_known_cve": {"type": "boolean"},
                            },
                        },
                    },
                    "total_deps_count": {"type": "integer"},
                    "outdated_count": {"type": "integer"},
                    "risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                },
            },
        ),
        SkillStep(
            name="test_coverage",
            description="Assess test coverage gaps and CI/CD maturity",
            prompt_template="""Assess test coverage for: {repo_name}
Language: {language}
Maintainability score: {maintainability_score}/100
Complexity rating: {avg_complexity_rating}

Return a JSON object:
{{
    "coverage_estimate_pct": integer 0-100,
    "has_unit_tests": true or false,
    "has_integration_tests": true or false,
    "has_ci_cd": true or false,
    "coverage_gaps": [
        "specific module or area lacking adequate tests"
    ],
    "test_quality_score": integer 0-100
}}

Return ONLY the JSON. No markdown fences, no explanation.""",
            output_schema={
                "type": "object",
                "required": [
                    "coverage_estimate_pct",
                    "has_unit_tests",
                    "has_integration_tests",
                    "has_ci_cd",
                    "coverage_gaps",
                    "test_quality_score",
                ],
                "properties": {
                    "coverage_estimate_pct": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "has_unit_tests": {"type": "boolean"},
                    "has_integration_tests": {"type": "boolean"},
                    "has_ci_cd": {"type": "boolean"},
                    "coverage_gaps": {"type": "array", "items": {"type": "string"}},
                    "test_quality_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
            },
        ),
        SkillStep(
            name="synthesise",
            description="Produce a prioritised remediation plan from all step findings",
            prompt_template="""Synthesise a health report for: {repo_name}

Findings from previous steps:
- Complexity: {avg_complexity_rating}, Maintainability: {maintainability_score}/100
- Deps: {outdated_count}/{total_deps_count} outdated, risk level: {risk_level}
- Test coverage: {coverage_estimate_pct}%, test quality: {test_quality_score}/100
- CI/CD present: {has_ci_cd}
- Repo type: {repo_type}, Last commit: {last_commit_age_days} days ago

Return a JSON object:
{{
    "health_score": integer 0-100,
    "verdict": "excellent|good|needs_attention|critical",
    "top_risks": ["risk description"],
    "remediation_plan": [
        {{
            "priority": integer 1-5 where 1 is most urgent,
            "action": "specific actionable step",
            "effort": "low|medium|high",
            "impact": "low|medium|high"
        }}
    ],
    "estimated_weeks": integer weeks to remediate
}}

Return ONLY the JSON. No markdown fences, no explanation.""",
            output_schema={
                "type": "object",
                "required": [
                    "health_score",
                    "verdict",
                    "top_risks",
                    "remediation_plan",
                    "estimated_weeks",
                ],
                "properties": {
                    "health_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["excellent", "good", "needs_attention", "critical"],
                    },
                    "top_risks": {"type": "array", "items": {"type": "string"}},
                    "remediation_plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["priority", "action", "effort", "impact"],
                            "properties": {
                                "priority": {"type": "integer"},
                                "action": {"type": "string"},
                                "effort": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                                "impact": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                            },
                        },
                    },
                    "estimated_weeks": {"type": "integer"},
                },
            },
        ),
    ],
)


# ── Critic Prompt ─────────────────────────────────────────────────────────────
#
# The critic is a focused sub-step that runs after dependency_check.
# Its job is to verify whether the version numbers are plausible — a common
# hallucination vector since the model must recall specific version strings.

DEPENDENCY_CRITIC_PROMPT = """You are a critic agent verifying dependency version data for: {repo_name}

The dependency_check step produced this output:
{dep_output}

Critically examine each dependency entry. Flag anything suspicious:
1. Version strings that seem invented or inconsistent with the repo's known pinned versions
2. Latest versions that contradict known release history
3. months_behind values inconsistent with the listed version numbers
4. Dependencies that don't actually belong to this project

Return a JSON object:
{{
    "overall_trust": "trusted|suspicious|unreliable",
    "flagged": [
        {{
            "dependency": "package name",
            "concern": "specific description of what looks wrong or uncertain",
            "confidence": "high|medium|low"
        }}
    ],
    "summary": "one sentence verdict on the reliability of this dependency data"
}}

Return ONLY the JSON. No markdown fences, no explanation."""


# ── Monolithic Prompt ─────────────────────────────────────────────────────────
#
# A single prompt that asks for everything at once. Used only for token comparison.
# This demonstrates the problem: one huge context with no intermediate validation.

MONOLITHIC_PROMPT = """You are an expert software engineer. Analyze the GitHub repository: {url}

Produce a complete engineering health report covering ALL of the following in one response:
1. Repository metadata (language, stars, activity, file count, repo type)
2. Code complexity hotspots (top 3-5 files with issues and severity ratings)
3. Static analysis metrics (complexity rating, type annotations, duplication, maintainability 0-100)
4. Dependency audit (key dependencies with pinned vs latest versions, months_behind, CVE flags)
5. Test coverage (estimated coverage %, unit/integration tests, CI/CD, coverage gaps)
6. Final health score (0-100), verdict, top risks, and a prioritised remediation plan

Be precise with version numbers and metrics. Return a comprehensive JSON object with all findings.
Return ONLY the JSON. No markdown fences, no explanation."""


# ── Core Utilities ────────────────────────────────────────────────────────────


def extract_json(text: str) -> str:
    """Strips markdown code fences and returns the bare JSON string from a model response.

    Handles both ```json ... ``` and ``` ... ``` fences. Returns the input unchanged
    if no fence is found — the model may have followed instructions and returned raw JSON.
    """
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def call_gemini(prompt: str, step_label: str = "") -> tuple:
    """Calls Gemini, displays styled input/output panels, and returns (text, prompt_tokens, output_tokens).

    A brief sleep is added between calls to stay within free-tier rate limits.
    Token counts come from response.usage_metadata; defaults to 0 if unavailable.
    """
    messages = [{"role": "user", "content": prompt}]
    _display_model_input(messages, step_label)

    time.sleep(1)  # avoid rate-limit errors on free tier
    response = _client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    text = response.text

    # usage_metadata fields may be None on some model versions
    prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    _display_model_output(text, step_label)
    return text, prompt_tokens, output_tokens


def validate_output(output: dict, schema: dict) -> tuple:
    """Validates a dict against a JSON Schema. Returns (is_valid, error_message).

    Uses jsonschema.validate; error_message is empty string on success.
    """
    try:
        jsonschema.validate(instance=output, schema=schema)
        return True, ""
    except jsonschema.ValidationError as e:
        return False, e.message


def build_retry_prompt(original_prompt: str, bad_output: str, error: str) -> str:
    """Appends the validation error and bad output to the original prompt for error correction.

    The model sees exactly what went wrong and can self-correct rather than guessing.
    """
    return (
        f"{original_prompt}\n\n"
        f"Your previous response failed validation with this error:\n"
        f"ERROR: {error}\n\n"
        f"Bad response was:\n{bad_output}\n\n"
        f"Please fix the response so it matches the schema exactly.\n"
        f"Return ONLY the corrected JSON. No markdown fences, no explanation."
    )


# ── Display Helpers ───────────────────────────────────────────────────────────


def _display_model_input(messages: list, label: str = "") -> None:
    """Renders the model input messages array in a bright_black panel with role-colored labels."""
    input_elements = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            label_style, content_style = "dim", "dim"
        elif role == "user":
            label_style, content_style = "bold blue", "blue"
        elif role == "assistant":
            label_style, content_style = "bold green", "green"
        else:
            label_style, content_style = "bold yellow", "yellow"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
        input_elements.append(
            Text.assemble((f"{role.upper()}: ", label_style), (wrapped, content_style))
        )
        input_elements.append(Rule(style="bright_black"))

    if input_elements:
        input_elements.pop()  # remove trailing rule

    title = (
        f"[bold bright_black]Model Input · {label}[/bold bright_black]"
        if label
        else "[bold bright_black]Model Input[/bold bright_black]"
    )
    console.print(
        Panel(
            Group(*input_elements),
            title=title,
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def _display_model_output(text: str, label: str = "") -> None:
    """Renders the raw model response text in a bright_black panel with an ASSISTANT label."""
    wrapped = textwrap.fill(text, width=82, subsequent_indent="           ")
    content = Text.assemble(("ASSISTANT: ", "bold green"), (wrapped, "italic"))

    title = (
        f"[bold bright_black]Model Response · {label}[/bold bright_black]"
        if label
        else "[bold bright_black]Model Response[/bold bright_black]"
    )
    console.print(
        Panel(
            content,
            title=title,
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ── Skill Executor ────────────────────────────────────────────────────────────


class SkillExecutor:
    """Runs a Skill step by step, passing each step's validated output into the next step's prompt."""

    def run_step(self, step: SkillStep, context: dict) -> StepResult:
        """Executes one skill step with automatic retry on schema or JSON parse failure.

        Builds the prompt from the step's template using the accumulated context dict.
        On validation failure, appends the error to the prompt and retries up to MAX_RETRIES times.
        Raises ValueError if all retries are exhausted.
        """
        prompt = step.prompt_template.format(**context)
        retries = 0

        while True:
            text, prompt_tokens, output_tokens = call_gemini(
                prompt, step_label=step.name
            )

            # Attempt JSON parse; bad JSON triggers the same retry path as schema failure
            try:
                output = json.loads(extract_json(text))
            except json.JSONDecodeError as e:
                if retries < MAX_RETRIES:
                    retries += 1
                    console.print(
                        f"  [yellow]⚠ JSON parse error (attempt {retries}): {e}[/yellow]"
                    )
                    prompt = build_retry_prompt(prompt, text, f"JSONDecodeError: {e}")
                    continue
                console.print(
                    f"[bold red]Error:[/bold red] '{step.name}' produced invalid JSON after {MAX_RETRIES} retries."
                )
                raise

            is_valid, error_msg = validate_output(output, step.output_schema)
            if is_valid:
                console.print(
                    f"  [bold green]✓[/bold green] [dim]schema valid[/dim]  "
                    f"[dim]in: {prompt_tokens} / out: {output_tokens} tokens[/dim]"
                )
                console.print()
                return StepResult(
                    step_name=step.name,
                    output=output,
                    prompt_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                    retries=retries,
                )

            # Schema invalid — correct-and-retry
            if retries < MAX_RETRIES:
                retries += 1
                console.print(
                    f"  [yellow]⚠ Schema validation failed (attempt {retries}): {error_msg}[/yellow]"
                )
                prompt = build_retry_prompt(prompt, text, error_msg)
            else:
                console.print(
                    f"[bold red]Error:[/bold red] '{step.name}' schema validation failed after {MAX_RETRIES} retries."
                )
                raise ValueError(
                    f"Step '{step.name}' failed schema validation: {error_msg}"
                )

    def run_critic(self, dep_result: StepResult, repo_name: str) -> StepResult:
        """Runs the critic sub-step after dependency_check to verify version data accuracy.

        The critic is itself a Gemini call with a focused prompt. It updates the StepResult
        in place: sets critic_flagged and appends to critic_issues. Token counts are cumulative.
        Returns the updated StepResult.
        """
        console.print(
            "[bold magenta]-- Critic Sub-Step: Verifying dependency data ----------[/bold magenta]"
        )
        console.print()

        critic_prompt = DEPENDENCY_CRITIC_PROMPT.format(
            repo_name=repo_name,
            dep_output=json.dumps(dep_result.output, indent=2),
        )

        text, prompt_tokens, output_tokens = call_gemini(
            critic_prompt, step_label="critic"
        )

        try:
            critic_output = json.loads(extract_json(text))
        except json.JSONDecodeError:
            console.print(
                "[yellow]  Critic returned non-JSON; skipping critic verdict.[/yellow]"
            )
            return dep_result

        # Add critic token costs to the dependency step totals
        dep_result.prompt_tokens += prompt_tokens
        dep_result.output_tokens += output_tokens

        trust = critic_output.get("overall_trust", "unknown")
        dep_result.critic_flagged = trust != "trusted"
        dep_result.critic_issues = [
            f["concern"] for f in critic_output.get("flagged", [])
        ]

        trust_color = (
            "green"
            if trust == "trusted"
            else "red" if trust == "unreliable" else "yellow"
        )
        console.print(
            f"  Critic verdict: [{trust_color}]{trust}[/{trust_color}]  "
            f"[dim]{len(dep_result.critic_issues)} item(s) flagged[/dim]"
        )

        if dep_result.critic_flagged:
            for issue in dep_result.critic_issues:
                console.print(f"  [yellow]⚠  {issue}[/yellow]")

        summary = critic_output.get("summary", "")
        if summary:
            console.print(f"  [dim]{summary}[/dim]")

        console.print()
        return dep_result

    def run_skill(self, skill: Skill, repo_url: str) -> SkillRun:
        """Executes all steps of a skill in sequence for a given repo URL.

        Context is a flat dict that starts with the URL and grows as each step's output
        is merged in. This lets later steps reference any field from earlier steps by name.
        Returns a SkillRun with all step results and the accumulated final context.
        """
        run = SkillRun(repo_url=repo_url)
        context = {"url": repo_url}  # seed context with the repo URL

        for idx, step in enumerate(skill.steps, 1):
            console.print(
                f"[bold cyan]-- Step {idx}/{len(skill.steps)}: {step.name} "
                f"------------------------------[/bold cyan]"
            )
            console.print(f"  [dim]{step.description}[/dim]")
            console.print()

            result = self.run_step(step, context)

            # Critic runs immediately after dependency_check before context is updated
            if step.name == "dependency_check":
                result = self.run_critic(result, context.get("repo_name", repo_url))

            run.step_results.append(result)
            context.update(result.output)  # flatten into context for downstream steps

        run.final_output = context
        return run

    def run_monolithic(self, repo_url: str) -> tuple:
        """Runs the monolithic single-prompt variant for token cost comparison.

        Returns (prompt_tokens, output_tokens). The response is displayed but not validated.
        """
        prompt = MONOLITHIC_PROMPT.format(url=repo_url)
        _, prompt_tokens, output_tokens = call_gemini(prompt, step_label="monolithic")
        return prompt_tokens, output_tokens


# ── Report Display ────────────────────────────────────────────────────────────


def display_health_report(run: SkillRun) -> None:
    """Prints the synthesised health report: score, verdict, and remediation plan table."""
    final = run.final_output
    repo = final.get("repo_name", run.repo_url)
    score = final.get("health_score", 0)
    verdict = final.get("verdict", "unknown").upper()

    score_color = "green" if score >= 75 else "yellow" if score >= 50 else "red"
    verdict_color = (
        "green"
        if verdict == "EXCELLENT"
        else "yellow" if verdict in ("GOOD", "NEEDS_ATTENTION") else "red"
    )

    console.print(Rule(f"[bold]Health Report: {repo}[/bold]", style="white"))
    console.print()
    console.print(f"  Health Score : [{score_color}]{score}/100[/{score_color}]")
    console.print(
        f"  Verdict      : [{verdict_color}][bold]{verdict}[/bold][/{verdict_color}]"
    )
    console.print(
        f"  Est. Remediation : [dim]{final.get('estimated_weeks', '?')} weeks[/dim]"
    )
    console.print()

    # Top risks
    risks = final.get("top_risks", [])
    if risks:
        console.print("  [bold]Top Risks:[/bold]")
        for risk in risks:
            console.print(f"  [red]•[/red] [dim]{risk}[/dim]")
        console.print()

    # Remediation plan table
    plan = final.get("remediation_plan", [])
    if plan:
        table = Table(
            show_header=True, header_style="bold", padding=(0, 2), show_edge=False
        )
        table.add_column("Pri", justify="center", style="bold", min_width=4)
        table.add_column("Action", min_width=42)
        table.add_column("Effort", justify="center")
        table.add_column("Impact", justify="center")

        for item in sorted(plan, key=lambda x: x.get("priority", 9)):
            effort_color = (
                "green"
                if item["effort"] == "low"
                else "yellow" if item["effort"] == "medium" else "red"
            )
            impact_color = (
                "green"
                if item["impact"] == "high"
                else "yellow" if item["impact"] == "medium" else "dim"
            )
            table.add_row(
                str(item["priority"]),
                item["action"],
                f"[{effort_color}]{item['effort']}[/{effort_color}]",
                f"[{impact_color}]{item['impact']}[/{impact_color}]",
            )

        console.print(table)
        console.print()


def display_token_comparison(runs: list) -> None:
    """Prints per-step token costs for each repo alongside the monolithic prompt totals.

    The overhead of multi-step execution buys schema validation and critic sub-steps —
    the table makes that trade-off visible in raw numbers.
    """
    console.print(
        Rule(
            "[bold yellow]Token Cost: Step-by-Step vs Monolithic[/bold yellow]",
            style="yellow",
        )
    )
    console.print()

    for run in runs:
        repo = run.final_output.get("repo_name", run.repo_url)
        console.print(f"[bold]{repo}[/bold]")

        table = Table(
            show_header=True, header_style="bold", show_lines=True, padding=(0, 2)
        )
        table.add_column("Step", min_width=22)
        table.add_column("In Tokens", justify="right")
        table.add_column("Out Tokens", justify="right")
        table.add_column("Total", justify="right", style="bold")
        table.add_column("Retries", justify="center")

        step_total_in = step_total_out = 0

        for sr in run.step_results:
            critic_note = " [magenta](+critic)[/magenta]" if sr.critic_flagged else ""
            retry_str = str(sr.retries) if sr.retries else "[dim]0[/dim]"
            table.add_row(
                sr.step_name + critic_note,
                str(sr.prompt_tokens),
                str(sr.output_tokens),
                str(sr.prompt_tokens + sr.output_tokens),
                retry_str,
            )
            step_total_in += sr.prompt_tokens
            step_total_out += sr.output_tokens

        table.add_section()
        table.add_row(
            "[bold]Steps Total[/bold]",
            f"[bold]{step_total_in}[/bold]",
            f"[bold]{step_total_out}[/bold]",
            f"[bold]{step_total_in + step_total_out}[/bold]",
            "",
        )
        table.add_row(
            "[dim]Monolithic[/dim]",
            f"[dim]{run.monolithic_prompt_tokens}[/dim]",
            f"[dim]{run.monolithic_output_tokens}[/dim]",
            f"[dim]{run.monolithic_prompt_tokens + run.monolithic_output_tokens}[/dim]",
            "[dim]n/a[/dim]",
        )

        console.print(table)

        step_total = step_total_in + step_total_out
        mono_total = run.monolithic_prompt_tokens + run.monolithic_output_tokens
        if mono_total > 0:
            delta = step_total - mono_total
            delta_pct = delta / mono_total * 100
            sign = "+" if delta >= 0 else ""
            color = "yellow" if delta >= 0 else "green"
            console.print(
                f"  [{color}]{sign}{delta} tokens ({sign}{delta_pct:.0f}%) vs monolithic[/{color}]  "
                f"[dim](overhead buys per-step schema validation + critic)[/dim]"
            )
        console.print()


def display_summary_table(runs: list) -> None:
    """Prints a side-by-side comparison of all three repos' final health metrics."""
    console.print(
        Rule("[bold yellow]Repository Comparison Summary[/bold yellow]", style="yellow")
    )
    console.print()

    table = Table(show_header=True, header_style="bold", show_lines=True)
    table.add_column("Repository", min_width=28)
    table.add_column("Type", justify="center")
    table.add_column("Health", justify="center")
    table.add_column("Verdict", justify="center")
    table.add_column("Deps Risk", justify="center")
    table.add_column("Coverage%", justify="center")
    table.add_column("Critic Alert", justify="center")
    table.add_column("Est. Weeks", justify="center")

    for run in runs:
        f = run.final_output
        repo = f.get("repo_name", run.repo_url)
        score = f.get("health_score", 0)
        verdict = f.get("verdict", "?")
        risk = f.get("risk_level", "?")
        coverage = f.get("coverage_estimate_pct", "?")
        weeks = f.get("estimated_weeks", "?")
        repo_type = f.get("repo_type", "?")

        score_color = "green" if score >= 75 else "yellow" if score >= 50 else "red"
        verdict_color = (
            "green"
            if verdict == "excellent"
            else "yellow" if verdict == "good" else "red"
        )
        risk_color = (
            "green" if risk == "low" else "yellow" if risk == "medium" else "red"
        )
        critic_flagged = any(sr.critic_flagged for sr in run.step_results)
        critic_str = "[red]YES[/red]" if critic_flagged else "[green]no[/green]"

        table.add_row(
            repo,
            repo_type,
            f"[{score_color}]{score}/100[/{score_color}]",
            f"[{verdict_color}]{verdict}[/{verdict_color}]",
            f"[{risk_color}]{risk}[/{risk_color}]",
            f"{coverage}%",
            critic_str,
            str(weeks),
        )

    console.print(table)
    console.print()


# ── Entry Point ───────────────────────────────────────────────────────────────

# Three repos chosen to demonstrate contrast:
# - fastapi  : healthy, active, well-typed Python project
# - docopt   : neglected, last meaningful commit ~2013, version data is uncertain
# - django   : large, monorepo-scale, well-maintained but complex
REPOS = [
    "https://github.com/tiangolo/fastapi",
    "https://github.com/docopt/docopt",
    "https://github.com/django/django",
]


def main():
    """Runs the repo-health-audit skill on three repos, then compares token costs against a monolithic prompt."""
    console.print(
        Panel.fit(
            "[bold yellow]Skill Executor: Repo Health Audit[/bold yellow]\n"
            "[dim]Multi-step skill decomposition with schema validation and critic sub-steps.[/dim]\n"
            f"[dim]Skill: repo-health-audit  ·  {len(REPO_HEALTH_SKILL.steps)} steps  ·  {len(REPOS)} repositories[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    executor = SkillExecutor()
    all_runs = []

    for repo_url in REPOS:
        console.print(Rule(f"[bold]Repository: {repo_url}[/bold]", style="white"))
        console.print()

        run = executor.run_skill(REPO_HEALTH_SKILL, repo_url)
        display_health_report(run)

        # Run monolithic prompt for the same repo to capture its token cost
        console.print(
            "[bold cyan]-- Monolithic Prompt (token comparison baseline) ------[/bold cyan]"
        )
        console.print()
        mono_in, mono_out = executor.run_monolithic(repo_url)
        run.monolithic_prompt_tokens = mono_in
        run.monolithic_output_tokens = mono_out
        console.print(
            f"  [dim]Monolithic: {mono_in} in / {mono_out} out  "
            f"({mono_in + mono_out} total)[/dim]"
        )
        console.print()

        all_runs.append(run)

    display_token_comparison(all_runs)
    display_summary_table(all_runs)


if __name__ == "__main__":
    main()
