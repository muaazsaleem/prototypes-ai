import os
import subprocess
from typing import Optional

# Maximum characters allowed for tool outputs to prevent context flooding.
MAX_OUTPUT_CHARS = 4000


def list_files(directory: str = ".") -> dict:
    """Recursively lists all files in a directory, excluding common noisy folders.

    Traverses the directory tree and returns a list of paths and the total count.
    Prunes 'venv', '.git', '__pycache__', '.pytest_cache', and 'node_modules'.
    """
    skip = {"venv", ".git", "__pycache__", ".pytest_cache", "node_modules"}
    found = []
    try:
        for root, dirs, files in os.walk(directory):
            # Mutate dirs in-place to prevent descending into skipped directories.
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for f in files:
                found.append(os.path.join(root, f))
        return {"files": found, "count": len(found)}
    except Exception as e:
        # Return error message if directory access fails.
        return {"error": str(e), "files": []}


def read_file(path: str) -> dict:
    """Reads the full text content of a file and returns it with a line count.

    Returns a dictionary containing the content and line count on success.
    Handles UTF-8 decoding and returns an error message on failure.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        # count() + 1 accounts for the final line if it doesn't end in newline.
        return {"content": content, "lines": content.count("\n") + 1}
    except Exception as e:
        return {"error": str(e), "content": ""}


def write_file(path: str, content: str) -> dict:
    """Writes the provided content to a file, creating parent directories if needed.

    Overwrites existing files at the path. Returns success status and path or error.
    Useful for applying fixes and creating new source/test files.
    """
    try:
        parent = os.path.dirname(path)
        if parent:
            # ensure parent directory exists before writing file
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_shell(command: str, cwd: Optional[str] = None) -> dict:
    """Executes a shell command and returns its output and exit code.

    Captures both stdout and stderr. Output is truncated to MAX_OUTPUT_CHARS.
    Includes a 60-second timeout to prevent hanging the agent loop.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd,
        )
        # Keep only the tail of the output to protect model context.
        stdout = result.stdout[-MAX_OUTPUT_CHARS:]
        stderr = result.stderr[-MAX_OUTPUT_CHARS:]
        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        # handle command timeout explicitly
        return {"stdout": "", "stderr": "Command timed out after 60s", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def run_tests(path: str = ".") -> dict:
    """Runs the pytest suite on the specified path and returns the outcome.

    Uses verbose output and short tracebacks for readability.
    Returns a 'passed' flag which is True only if pytest exits with code 0.
    """
    result = subprocess.run(
        f"python -m pytest {path} -v --tb=short --no-header",
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Combine stdout and stderr then truncate to protect context.
    output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    return {
        "output": output,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
    }


def run_linter(path: str = ".") -> dict:
    """Checks the code style and syntax of the specified path using flake8.

    Enforces a 100-character line limit and ignores the venv directory.
    Returns the linter output and a 'clean' flag indicating if no violations were found.
    """
    result = subprocess.run(
        f"python -m flake8 {path} --max-line-length=100 --exclude=venv",
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # capture violation details for the agent to fix
    output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    return {
        "output": output,
        "clean": result.returncode == 0,
    }


# Registry for tool dispatching by name.
TOOL_REGISTRY = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_shell": run_shell,
    "run_tests": run_tests,
    "run_linter": run_linter,
}

# List of functions exported as tools to the Gemini SDK.
TOOLS = [list_files, read_file, write_file, run_shell, run_tests, run_linter]
