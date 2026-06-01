#!/usr/bin/env python3
"""
Sub-Agent Worker
================
This script IS the sub-agent. The orchestrator spawns it as a subprocess.

Communication contract:
  - STDIN:  one JSON line  { "agent_id": str, "task": str }
  - STDOUT: one JSON line  { "agent_id": str, "result": str, "status": "ok"|"error" }
  - STDERR: debug logs (visible in terminal, not captured by orchestrator)

This is the plumbing that agent SDKs (LangGraph, CrewAI, AutoGen) hide from you.
Without a framework you own: process lifecycle, the stdin/stdout protocol,
serialization, and making sure the process actually exits cleanly.
"""

import json
import os
import sys

from google import genai
from google.genai import types


def main() -> None:
    # ── 1. Read task from stdin (the inter-process message) ───────────────────
    raw = sys.stdin.read().strip()
    if not raw:
        out = {"agent_id": "unknown", "result": "", "status": "error",
               "error": "empty stdin"}
        print(json.dumps(out))
        sys.exit(1)

    try:
        task_msg = json.loads(raw)
        agent_id: str = task_msg["agent_id"]
        task: str = task_msg["task"]
    except (json.JSONDecodeError, KeyError) as exc:
        out = {"agent_id": "unknown", "result": "", "status": "error",
               "error": f"bad task payload: {exc}"}
        print(json.dumps(out))
        sys.exit(1)

    print(f"[subagent:{agent_id}] started — task: {task[:60]}…", file=sys.stderr)

    # ── 2. Call Gemini 2.5 Flash ───────────────────────────────────────────────
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        prompt = (
            f"You are a focused research specialist. Your task:\n\n{task}\n\n"
            "Write a concise but insightful paragraph (4-6 sentences). "
            "Be specific and factual."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=400,
            ),
        )

        result_text = response.text.strip()
        status = "ok"
        print(f"[subagent:{agent_id}] finished — {len(result_text)} chars",
              file=sys.stderr)

    except Exception as exc:
        result_text = ""
        status = "error"
        error_msg = str(exc)
        print(f"[subagent:{agent_id}] ERROR: {error_msg}", file=sys.stderr)
        out = {"agent_id": agent_id, "result": result_text,
               "status": status, "error": error_msg}
        # ── 3. Write result to stdout (the reply message) ─────────────────────
        print(json.dumps(out))
        sys.exit(1)

    out = {"agent_id": agent_id, "result": result_text, "status": status}
    # ── 3. Write result to stdout (the reply message) ─────────────────────────
    print(json.dumps(out))


if __name__ == "__main__":
    main()
