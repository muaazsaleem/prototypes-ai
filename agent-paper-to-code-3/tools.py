"""
Tools available to the ReAct agent.

Each tool follows the pattern:
  fn(args, paper_text) -> (result_str, is_done, final_code | None)

`is_done` is True only for the `finish` tool.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import tempfile
import os
from typing import Any

# ---------------------------------------------------------------------------
# Scratch buffer -- shared mutable state for write_code / run_code / finish
# ---------------------------------------------------------------------------
_scratch: dict[str, str] = {"code": ""}

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use format)
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    {
        "name": "extract_section",
        "description": (
            "Extract a named section from the paper text for closer inspection. "
            "Useful for focusing on the algorithm, experiments, or pseudocode section."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_name": {
                    "type": "string",
                    "description": (
                        "Name or keyword of the section to extract "
                        "(e.g. 'algorithm', 'method', 'experiment', 'abstract')."
                    ),
                }
            },
            "required": ["section_name"],
        },
    },
    {
        "name": "write_code",
        "description": (
            "Write Python code to the scratch buffer. "
            "This REPLACES whatever was there before. "
            "Always write the COMPLETE file -- do not write partial patches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Complete Python source code to write.",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "run_code",
        "description": (
            "Execute the current scratch buffer in a subprocess. "
            "Returns stdout and stderr. Use this to verify correctness."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Max seconds to wait (default 30).",
                    "default": 30,
                }
            },
            "required": [],
        },
    },
    {
        "name": "bash",
        "description": (
            "Execute a bash shell command. "
            "Returns the exit code, stdout, and stderr. "
            "Use this tool to run tests, install packages, check system status, "
            "or run shell commands if required to fulfill the task."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact bash command to run.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Max seconds to wait (default 30).",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "finish",
        "description": (
            "Save the current scratch buffer as the final output and terminate. "
            "Only call this after run_code has confirmed the code works."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One-paragraph summary of what was implemented.",
                }
            },
            "required": ["summary"],
        },
    },
]

# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------

def _tool_extract_section(args: dict, paper_text: str) -> tuple[str, bool, None]:
    keyword = args.get("section_name", "").lower()
    lines = paper_text.split("\n")

    # Find lines that look like section headers containing the keyword
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if keyword in stripped and (
            stripped.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9", "#"))
            or len(stripped) < 80
        ):
            start = i
            break

    if start is None:
        # Fall back: return lines that mention the keyword
        matches = [l for l in lines if keyword in l.lower()]
        if matches:
            excerpt = "\n".join(matches[:60])
            return f"[keyword matches]\n{excerpt}", False, None
        return f"Section '{keyword}' not found.", False, None

    # Return up to 100 lines from that point
    excerpt = "\n".join(lines[start : start + 100])
    return excerpt, False, None


def _tool_write_code(args: dict, paper_text: str) -> tuple[str, bool, None]:
    code = args.get("code", "")
    _scratch["code"] = code
    lines = code.count("\n") + 1
    return f"Written {lines} lines to scratch buffer.", False, None


def _tool_run_code(args: dict, paper_text: str) -> tuple[str, bool, None]:
    code = _scratch.get("code", "")
    if not code.strip():
        return "ERROR: scratch buffer is empty. Call write_code first.", False, None

    timeout = int(args.get("timeout_seconds", 30))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="p2c_"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout[-3000:] if result.stdout else ""
        stderr = result.stderr[-2000:] if result.stderr else ""
        rc = result.returncode
        summary = f"exit_code={rc}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        return summary.strip(), False, None
    except subprocess.TimeoutExpired:
        return f"ERROR: code timed out after {timeout}s.", False, None
    finally:
        os.unlink(tmp_path)


def _tool_bash(args: dict, paper_text: str) -> tuple[str, bool, None]:
    command = args.get("command", "")
    if not command.strip():
        return "ERROR: no command provided.", False, None

    timeout = int(args.get("timeout_seconds", 30))

    try:
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout[-3000:] if result.stdout else ""
        stderr = result.stderr[-2000:] if result.stderr else ""
        rc = result.returncode
        summary = f"exit_code={rc}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        return summary.strip(), False, None
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s.", False, None


def _tool_finish(args: dict, paper_text: str) -> tuple[str, bool, str]:
    summary = args.get("summary", "")
    code = _scratch.get("code", "")
    if not code.strip():
        return "ERROR: cannot finish with empty scratch buffer.", False, None
    msg = f"Done.\n\nSummary: {summary}"
    return msg, True, code


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_TOOLS = {
    "extract_section": _tool_extract_section,
    "write_code": _tool_write_code,
    "run_code": _tool_run_code,
    "bash": _tool_bash,
    "finish": _tool_finish,
}


def dispatch_tool(
    name: str, args: dict[str, Any], paper_text: str
) -> tuple[str, bool, str | None]:
    """
    Route a tool call to its implementation.

    Returns:
        (result_str, is_done, final_code | None)
    """
    fn = _TOOLS.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'.", False, None
    return fn(args, paper_text)
