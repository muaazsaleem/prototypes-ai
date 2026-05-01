"""
Coding Agent — ReAct loop with Reflexion over a codebase.

Loop structure (per attempt):
  1. Build prompt  →  includes task + working memory + past reflections
  2. ReAct         →  model reasons and calls tools (read/write/test/shell) in a loop
  3. Verify        →  framework runs the test suite directly
  4. Reflexion     →  on failure, ask the model to reflect; store reflection in memory
  5. Retry or escalate
"""

import os
import textwrap

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from memory import WorkingMemory
from tools import TOOL_REGISTRY, TOOLS, run_tests

console = Console()

SYSTEM_PROMPT = """You are an expert coding agent. Your job is to analyse a code repository,
understand what is broken, and fix it so that all tests pass.

Available tools:
  list_files  — explore the repo structure
  read_file   — read any file
  write_file  — create or overwrite a file with corrected code
  run_shell   — run arbitrary shell commands
  run_tests   — execute the pytest suite
  run_linter  — check code style with flake8

Follow the ReAct pattern on every turn:
  Observe  → list files and read relevant source + test files
  Plan     → reason (in plain text) about what is wrong
  Act      → make precise edits using write_file
  Verify   → run_tests to confirm your fix

Rules:
  - Always start by listing files to understand the structure.
  - Read test files first — they define the expected behaviour.
  - Make minimal, targeted edits; do not rewrite entire files unnecessarily.
  - After every write_file call, run the linter to catch syntax errors early.
  - Call run_tests to verify before declaring yourself done.
"""


class CodingAgent:
    """Orchestrates the ReAct + Reflexion loop to fix bugs in a codebase.

    Maintains state across multiple attempts, uses tools to interact with the
    file system, and leverages Gemini for reasoning and reflection.
    """

    def __init__(self, repo_path: str = ".", max_iterations: int = 5):
        """Initialises the agent with repository path and iteration budget.

        Sets up the Gemini client, chat configuration, and working memory.
        Resolves repo_path to an absolute path for consistency.
        """
        self.repo_path = os.path.abspath(repo_path)
        self.max_iterations = max_iterations
        self.memory = WorkingMemory()

        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        # Shared config reused for every chat session.
        self.chat_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,  # SDK auto-generates OpenAPI schemas from these Python functions
            # Disable automatic execution so we control tool calls ourselves.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

    def run(self, task: str) -> bool:
        """Main entry point that executes the high-level attempt loop.

        Returns True if the task is successfully verified by tests, False otherwise.
        Manages the transition between ReAct acting phase and Reflexion diagnosis phase.
        """
        # Display the task header using the terminal-output-style convention.
        console.print(
            Panel.fit(
                f"[bold yellow]Coding Agent[/bold yellow]\n"
                f"[dim]ReAct + Reflexion loop for: {task}[/dim]\n"
                f"[dim]Repo: {self.repo_path} | Max Iterations: {self.max_iterations}[/dim]",
                border_style="yellow",
            )
        )
        console.print()

        # One chat session for the entire run; reflections are injected as messages.
        chat = self.client.chats.create(
            model="gemini-2.0-flash", config=self.chat_config
        )

        for attempt in range(self.max_iterations):
            self.memory.attempts = attempt + 1
            console.print(
                Rule(
                    f"[bold blue]Attempt {attempt + 1} / {self.max_iterations}[/bold blue]",
                    style="blue",
                )
            )
            console.print()

            prompt = self._build_prompt(task, attempt)
            self._react_loop(chat, prompt)

            # Framework-level test check (not a tool call — we verify independently).
            console.print("\n[yellow]▶ Framework verifying test suite…[/yellow]")
            result = run_tests(self.repo_path)

            if result["passed"]:
                console.print()
                console.print(
                    Rule("[bold green]Overall Summary[/bold green]", style="yellow")
                )
                console.print()
                console.print(
                    Panel(
                        "[bold green]✓ All tests pass — task complete![/bold green]",
                        border_style="green",
                    )
                )
                return True

            console.print(
                f"[red]✗ Tests still failing after attempt {attempt + 1}.[/red]"
            )

            # Reflexion: not another attempt blindly — ask the model to diagnose.
            if attempt < self.max_iterations - 1:
                reflection = self._reflexion_step(chat, result["output"])
                self.memory.add_reflection(reflection)

        console.print()
        console.print(Rule("[bold red]Overall Summary[/bold red]", style="yellow"))
        console.print()
        console.print(
            Panel(
                "[bold red]Max iterations reached — escalating to human review.[/bold red]",
                border_style="red",
            )
        )
        return False

    def _build_prompt(self, task: str, attempt: int) -> str:
        """Constructs the prompt for the current attempt, including memory.

        Injects files read/modified and past reflections into retries to
        guide the model away from previous failures.
        """
        if attempt == 0:
            return (
                f"Task: {task}\n\n"
                f"Repository root: {self.repo_path}\n\n"
                "Start by listing the files, read the test file(s) to understand "
                "expected behaviour, read the source file(s) to find bugs, fix them, "
                "and run the tests to verify."
            )
        # Subsequent attempts include the full working memory (with past reflections).
        return (
            f"Task (retry): {task}\n\n"
            f"Repository root: {self.repo_path}\n\n"
            f"Working memory:\n{self.memory.format_for_prompt()}\n\n"
            "Apply your reflection from above. Make the necessary corrections and "
            "run the tests to verify."
        )

    def _react_loop(self, chat, initial_prompt: str) -> None:
        """Drives the model through Reason-Act-Observe cycles.

        Continues until the model provides a final answer with no more tool calls.
        Styles LLM inputs and responses using the terminal-output-style skill.
        """
        self._display_llm_input("user", initial_prompt)
        response = chat.send_message(initial_prompt)
        self._display_llm_response(response)

        while True:
            calls = self._extract_function_calls(response)
            if not calls:
                # model finished acting
                break

            response_parts = []
            for fc in calls:
                tool_result = self._execute_tool(fc.name, dict(fc.args))
                # bundle tool result as a part for the next message
                response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": str(tool_result)},
                    )
                )

            # display tool results being fed back to the model
            input_text = "\n".join([str(p.function_response) for p in response_parts])
            self._display_llm_input("tool", input_text)

            response = chat.send_message(response_parts)
            self._display_llm_response(response)

    def _execute_tool(self, name: str, args: dict):
        """Invokes a tool by name, logs the action, and updates memory.

        Truncates arguments for display and marks files as read or modified
        in the agent's working memory.
        """
        display_args = self._format_args(args)
        console.print(f"  [cyan]⚙ {name}[/cyan]({display_args})")

        result = TOOL_REGISTRY[name](**args)

        # track file interactions in memory
        if name == "read_file":
            self.memory.mark_read(args.get("path", ""))
        elif name == "write_file":
            path = args.get("path", "")
            self.memory.mark_modified(path)
            console.print(f"    [green]✓ wrote {path}[/green]")
        elif name == "run_tests":
            status = (
                "[green]PASSED[/green]" if result.get("passed") else "[red]FAILED[/red]"
            )
            console.print(f"    Tests → {status}")

        return result

    def _reflexion_step(self, chat, test_output: str) -> str:
        """Asks the model to diagnose failure and plan the next attempt.

        Feeds the test traceback and memory into the model and returns
        the text reflection to be stored in memory.
        """
        console.print()
        console.print(
            "[bold yellow]-- Reflexion --------------------------------------[/bold yellow]"
        )
        console.print()

        prompt = (
            "The tests are still failing. Here is the pytest output:\n\n"
            f"```\n{test_output[-2000:]}\n```\n\n"
            f"Working memory:\n{self.memory.format_for_prompt()}\n\n"
            "Diagnose the root cause of the remaining failures. "
            "State exactly which lines in which files are wrong and what the correct fix is. "
            "Be specific — this reflection will guide your next attempt."
        )

        self._display_llm_input("user", prompt)
        response = chat.send_message(prompt)
        self._display_llm_response(response)

        try:
            reflection_text = response.text
        except Exception:
            reflection_text = "(model returned no text in reflection)"

        return reflection_text

    def _display_llm_input(self, role: str, content: str):
        """Styles and displays LLM input according to terminal-output-style."""
        input_elements = []

        if role == "system":
            label_style = "dim"
            content_style = "dim"
        elif role == "user":
            label_style = "bold blue"
            content_style = "blue"
        elif role == "assistant":
            label_style = "bold green"
            content_style = "green"
        elif role == "tool":
            label_style = "bold yellow"
            content_style = "yellow"
        else:
            label_style = "white"
            content_style = "white"

        indent = " " * (len(role) + 2)
        wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)

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

    def _display_llm_response(self, response):
        """Styles and displays LLM response according to terminal-output-style."""
        try:
            # model may return text or function calls
            text = (
                response.text
                if response.text
                else str(response.candidates[0].content.parts)
            )
        except Exception:
            text = "(no displayable content)"

        wrapped_response = textwrap.fill(
            text, width=82, subsequent_indent="           "
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

    @staticmethod
    def _extract_function_calls(response) -> list:
        """Extracts tool call requests from a Gemini response part.

        Safely parses candidate content parts to find FunctionCall objects.
        """
        calls = []
        try:
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name:
                    calls.append(part.function_call)
        except Exception:
            pass
        return calls

    @staticmethod
    def _format_args(args: dict) -> str:
        """Formats tool arguments into a compact string for logging.

        Truncates long values to maintain terminal readability.
        """
        parts = []
        for k, v in args.items():
            s = repr(v)
            if len(s) > 60:
                s = s[:57] + "..."
            parts.append(f"{k}={s}")
        return ", ".join(parts)
