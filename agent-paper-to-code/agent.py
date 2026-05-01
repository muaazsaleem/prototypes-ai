import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from google import genai
from google.genai import types

from config import GEMINI_MODEL
from tools import TOOL_REGISTRY, TOOLS


def _execute_parallel(function_calls) -> List[Tuple]:
    """
    Run every tool call concurrently in a thread pool.
    Gemini 2.5 Flash can request multiple tools in a single turn; executing
    them in parallel cuts wall-clock latency when the calls are independent
    (e.g. searching repos and fetching a file at the same time).

    Returns a list of (function_call, result_dict) pairs in completion order.
    """

    def run_one(fc):
        """Execute a single function call and return (fc, result_dict).

        fc.args is a MapComposite from the SDK; dict() converts it to a plain dict
        so it can be unpacked as keyword arguments.
        """
        func = TOOL_REGISTRY.get(fc.name)
        if func is None:
            return fc, {"error": f"Unknown tool: {fc.name}"}
        try:
            return fc, func(**dict(fc.args))
        except Exception as exc:
            return fc, {"error": str(exc)}

    with ThreadPoolExecutor(max_workers=len(function_calls)) as pool:
        futures = [pool.submit(run_one, fc) for fc in function_calls]
        return [f.result() for f in as_completed(futures)]


def run_agent(
    client: genai.Client,
    paper_chunks: List[str],
    metadata: Dict,
    verbose: bool = True,
) -> Tuple[str, List[Dict]]:
    """
    Run the Paper-to-Code agent loop.

    The loop works as follows:
      1. Send the paper context + implementation request to Gemini.
      2. If the model issues tool calls (e.g. search GitHub), execute them —
         possibly in parallel — and feed results back.
      3. Repeat until the model produces a final text response (no more tool calls).

    Returns:
        (generated_code, tool_call_log)
        tool_call_log is a list of dicts recording every tool invocation.
    """
    context = "\n\n---\n\n".join(paper_chunks)

    prompt = f"""You are an expert ML engineer who turns academic papers into clean, runnable Python.

Paper title : {metadata.get("title", "Unknown")}
Core method : {metadata.get("method", "Unknown")}

Relevant paper excerpts:
{context}

Your task
---------
1. Use the available tools to search GitHub for existing implementations of the method.
   Issue multiple search calls in ONE turn when the queries are independent (parallel use).
2. Study any code you retrieve to understand the typical implementation pattern.
3. Write a complete, well-commented Python implementation of the paper's core method.
   Include a small if __name__ == "__main__" block that demos the code.

Return ONLY the Python code as your final message — no markdown fences, no prose.
"""

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        tools=TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
    )
    tool_call_log: List[Dict] = []

    for turn in range(6):
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config
        )
        model_content = response.candidates[0].content
        contents.append(model_content)

        function_calls = [
            p.function_call for p in model_content.parts if p.function_call
        ]

        if not function_calls:
            # No tool calls means the model is done — extract the final text
            code = "".join(p.text for p in model_content.parts if p.text)
            if verbose:
                print(f"  [agent] finished in {turn + 1} turn(s)")
            return code.strip(), tool_call_log

        if verbose:
            names = [fc.name for fc in function_calls]
            print(f"  [agent] turn {turn + 1} — calling {names} in parallel")

        # Execute all requested tools concurrently
        call_results = _execute_parallel(function_calls)

        # Record what was called and build the function-response parts for the next turn
        response_parts = []
        for fc, result in call_results:
            tool_call_log.append(
                {"tool": fc.name, "args": dict(fc.args), "result": result}
            )
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result, indent=2)},
                    )
                )
            )

        # Feed tool results back as a user turn so the model can continue reasoning
        contents.append(types.Content(role="user", parts=response_parts))

    return "# Agent hit the turn limit without producing output.", tool_call_log
