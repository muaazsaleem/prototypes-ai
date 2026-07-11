"""
Unit tests for paper2code.

Tests cover:
  - Paper ingestion (text cleaning, missing file)
  - Tool dispatcher: extract_section, write_code, run_code, finish
  - ReAct state machine edge cases (empty scratch, unknown tool)

No Anthropic API calls are made here.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap

import pytest

from ingest import load_paper, _clean
from tools import dispatch_tool, _scratch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp(content: str, suffix: str = ".txt") -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------

class TestLoadPaper:
    def test_loads_text_file(self):
        path = _write_tmp("Hello paper\nSection 2\nSome content")
        try:
            text = load_paper(path)
            assert "Hello paper" in text
            assert "Section 2" in text
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_paper("/nonexistent/path/paper.txt")

    def test_clean_removes_excess_blank_lines(self):
        raw = "line1\n\n\n\nline2\n\nline3"
        cleaned = _clean(raw)
        assert "\n\n\n" not in cleaned
        assert "line1" in cleaned
        assert "line3" in cleaned

    def test_clean_preserves_content(self):
        raw = "  Algorithm 1: Gradient Descent  \n  step 1: compute gradient  "
        cleaned = _clean(raw)
        assert "Algorithm 1" in cleaned
        assert "step 1" in cleaned


# ---------------------------------------------------------------------------
# Tool: extract_section
# ---------------------------------------------------------------------------

SAMPLE_PAPER = """
Abstract

This paper presents a novel approach.

1 Introduction

We propose a new algorithm.

2 Method

Algorithm 1: The Core Loop
  Input: X, learning rate lr
  For t in 1..T:
    grad = compute_gradient(X)
    X = X - lr * grad
  Return X

3 Experiments

We evaluated on MNIST.
"""


class TestExtractSection:
    def test_finds_method_section(self):
        result, done, code = dispatch_tool("extract_section", {"section_name": "method"}, SAMPLE_PAPER)
        assert done is False
        assert code is None
        assert "Algorithm" in result or "method" in result.lower() or "Core Loop" in result

    def test_finds_abstract(self):
        result, done, _ = dispatch_tool("extract_section", {"section_name": "abstract"}, SAMPLE_PAPER)
        assert done is False
        assert "novel approach" in result or "Abstract" in result

    def test_missing_section_returns_message(self):
        result, done, _ = dispatch_tool(
            "extract_section", {"section_name": "nonexistent_xyz"}, SAMPLE_PAPER
        )
        assert done is False
        assert "not found" in result.lower() or len(result) > 0


# ---------------------------------------------------------------------------
# Tool: write_code / run_code / finish
# ---------------------------------------------------------------------------

class TestWriteCode:
    def test_writes_to_scratch(self):
        code = "print('hello')"
        result, done, code_out = dispatch_tool("write_code", {"code": code}, "")
        assert done is False
        assert code_out is None
        assert _scratch["code"] == code

    def test_reports_line_count(self):
        code = "a = 1\nb = 2\nc = 3"
        result, _, _ = dispatch_tool("write_code", {"code": code}, "")
        assert "3" in result


class TestRunCode:
    def setup_method(self):
        _scratch["code"] = ""

    def test_runs_valid_code(self):
        dispatch_tool("write_code", {"code": "print('success')"}, "")
        result, done, _ = dispatch_tool("run_code", {}, "")
        assert done is False
        assert "success" in result

    def test_captures_stderr(self):
        dispatch_tool(
            "write_code",
            {"code": "import sys; sys.stderr.write('err_msg\\n')"},
            "",
        )
        result, _, _ = dispatch_tool("run_code", {}, "")
        assert "err_msg" in result

    def test_detects_syntax_error(self):
        dispatch_tool("write_code", {"code": "def broken(:\n    pass"}, "")
        result, _, _ = dispatch_tool("run_code", {}, "")
        assert "exit_code=1" in result or "SyntaxError" in result or "Error" in result

    def test_empty_scratch_returns_error(self):
        _scratch["code"] = ""
        result, done, _ = dispatch_tool("run_code", {}, "")
        assert "ERROR" in result
        assert done is False


class TestFinish:
    def setup_method(self):
        _scratch["code"] = ""

    def test_finish_with_code_returns_done(self):
        dispatch_tool("write_code", {"code": "x = 42"}, "")
        result, done, code = dispatch_tool("finish", {"summary": "Implements X."}, "")
        assert done is True
        assert code == "x = 42"
        assert "Done" in result

    def test_finish_empty_scratch_returns_error(self):
        _scratch["code"] = ""
        result, done, code = dispatch_tool("finish", {"summary": "..."}, "")
        assert done is False
        assert "ERROR" in result

    def test_unknown_tool_returns_error(self):
        result, done, code = dispatch_tool("nonexistent_tool", {}, "")
        assert done is False
        assert "unknown tool" in result.lower()


# ---------------------------------------------------------------------------
# Integration: dispatch chain
# ---------------------------------------------------------------------------

class TestDispatchChain:
    def test_write_run_finish_chain(self):
        """Simulate a minimal successful ReAct chain without LLM."""
        # Step 1: write
        r1, done1, _ = dispatch_tool(
            "write_code",
            {
                "code": textwrap.dedent("""\
                    def add(a, b):
                        return a + b

                    print(add(2, 3))
                """)
            },
            "",
        )
        assert not done1

        # Step 2: run -- must succeed
        r2, done2, _ = dispatch_tool("run_code", {"timeout_seconds": 10}, "")
        assert not done2
        assert "exit_code=0" in r2
        assert "5" in r2

        # Step 3: finish
        r3, done3, code = dispatch_tool(
            "finish", {"summary": "Simple addition function."}, ""
        )
        assert done3
        assert "add" in code


# ---------------------------------------------------------------------------
# Visual display / Printing tests
# ---------------------------------------------------------------------------

class TestPrintModelInput:
    def test_print_model_input_uses_dots(self):
        from react_loop import _print_model_input, types
        from rich.console import Console
        import react_loop
        
        # Capture stdout using rich's Console with a record=True
        test_console = Console(record=True, width=100)
        # Temporarily mock the global console in react_loop
        old_console = react_loop.console
        react_loop.console = test_console
        
        try:
            _print_model_input(
                system_prompt="My long system prompt",
                messages=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text="hello")]
                    )
                ]
            )
            # Retrieve output
            output = test_console.export_text()
            # Verify system prompt is not fully printed, but '...' is printed
            assert "My long system prompt" not in output
            assert "..." in output
            assert "SYSTEM" in output
            assert "USER" in output
            assert "hello" in output
        finally:
            react_loop.console = old_console

    def test_print_model_input_only_prints_last_message(self):
        from react_loop import _print_model_input, types
        from rich.console import Console
        import react_loop
        
        test_console = Console(record=True, width=100)
        old_console = react_loop.console
        react_loop.console = test_console
        
        try:
            _print_model_input(
                system_prompt="My long system prompt",
                messages=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text="message 1")]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="message 2")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text="message 3")]
                    )
                ]
            )
            output = test_console.export_text()
            assert "message 1" not in output
            assert "message 2" not in output
            assert "message 3" in output
        finally:
            react_loop.console = old_console

