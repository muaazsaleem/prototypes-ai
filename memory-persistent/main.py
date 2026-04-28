#!/usr/bin/env python3
"""
Memory That Persists Across Sessions
======================================
Demonstrates the fundamental difference between in-context (ephemeral) memory
and external (persistent) memory in LLM-based agents.

Experiment:
  Part 1 — No-memory agent
    Session 1: 3-turn conversation where the user shares personal facts.
    Session 2: New session starts fresh. The agent remembers nothing.

  Part 2 — External memory agent
    Session 1: Same 3 turns, but facts are extracted and written to a JSON file
               after every turn.
    Session 2: New session with a blank in-context history, but the agent reads
               from the file and retrieves relevant facts by keyword — so it
               "remembers" what was shared before.

Key concept:
  In-context memory lives only for the duration of one session (the messages
  list). External memory survives because it is written to disk and explicitly
  loaded at the start of each new turn.
"""

import json
import os
import re
import textwrap
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ─── Configuration ────────────────────────────────────────────────────────────

MODEL = "gemini-2.0-flash"
MEMORY_FILE = Path("memory_store.json")

# Common English words that carry no semantic meaning for retrieval
STOP_WORDS = {
    "i",
    "my",
    "the",
    "a",
    "an",
    "is",
    "am",
    "are",
    "do",
    "what",
    "how",
    "and",
    "or",
    "in",
    "of",
    "to",
    "for",
    "on",
    "at",
    "by",
    "with",
    "that",
    "this",
    "me",
    "you",
    "your",
    "it",
}

# ─── Conversation script (identical for both agents) ─────────────────────────

# Session 1: user shares facts about themselves
SESSION_1_TURNS = [
    "Hi! My name is Alex. I'm a backend engineer at a fintech startup.",
    "I mostly work in Python, but I've been exploring Rust lately for performance-critical parts.",
    "I'm currently building a real-time fraud detection system that needs to handle 10k transactions per second.",
]

# Session 2: user asks the agent to recall what was shared — nothing is re-stated
SESSION_2_TURNS = [
    "What's my name and what do I do for work?",
    "What programming languages do I work with?",
    "What project am I building and what are its performance requirements?",
]

# ─── External Memory Store ────────────────────────────────────────────────────


def load_memory() -> list[dict]:
    """Reads all stored memory entries from the JSON file on disk.

    Returns:
        A list of memory dictionary entries, or an empty list if the file is absent.

    Side effects:
        Reads from memory_store.json on the filesystem.
    """
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE) as f:
        return json.load(f).get("entries", [])


def save_memory(entries: list[dict]) -> None:
    """Persists the current list of memory entries back to disk.

    Args:
        entries: A list of memory dictionaries to serialize.

    Side effects:
        Overwrites memory_store.json with a new JSON structure.
    """
    with open(MEMORY_FILE, "w") as f:
        json.dump({"entries": entries}, f, indent=2)


def stem(word: str) -> str:
    """Provides minimal stemming by stripping trailing 's' characters.

    Args:
        word: The string to be stemmed.

    Returns:
        The word with a trailing 's' removed, provided it's longer than 3 chars.
    """
    # Only stem plurals or verbs ending in 's' if the root is substantial
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def retrieve_relevant(query: str, entries: list[dict]) -> list[dict]:
    """Retrieves memory entries that keyword-match the provided user query.

    Args:
        query: The raw string query from the user.
        entries: A list of stored memory dictionaries.

    Returns:
        A list of memory dictionaries that have keyword overlap with the query.
    """
    # Extract words, lower-case them, discard stop words, and stem the rest
    tokens = {stem(w) for w in re.findall(r"\w+", query.lower()) if w not in STOP_WORDS}

    # Return any entry where at least one stored keyword matches our query tokens
    return [e for e in entries if tokens & {stem(k) for k in e["keywords"]}]


def log_llm_interaction(
    system_instruction: str | None, contents: list | str, response_text: str
):
    """Logs the model input and response according to terminal-output-style.

    Args:
        system_instruction: The system prompt, if any.
        contents: Either a simple string prompt or a list of types.Content objects.
        response_text: The text returned by the model.

    Side effects:
        Prints formatted text to the terminal via rich.
    """
    input_elements = []

    if system_instruction:
        wrapped = textwrap.fill(
            system_instruction, width=82, subsequent_indent="        "
        )
        input_elements.append(Text.assemble(("SYSTEM: ", "dim"), (wrapped, "dim")))
        input_elements.append(Rule(style="bright_black"))

    if isinstance(contents, str):
        wrapped = textwrap.fill(contents, width=82, subsequent_indent="      ")
        input_elements.append(Text.assemble(("USER: ", "bold blue"), (wrapped, "blue")))
    else:
        for content in contents:
            role = content.role
            text = "".join(p.text for p in content.parts if p.text)

            if role == "user":
                label_style, content_style, role_label = "bold blue", "blue", "USER"
            elif role == "model":
                label_style, content_style, role_label = (
                    "bold green",
                    "green",
                    "ASSISTANT",
                )
            else:
                label_style, content_style, role_label = "dim", "dim", role.upper()

            indent = " " * (len(role_label) + 2)
            wrapped = textwrap.fill(text, width=82, subsequent_indent=indent)
            input_elements.append(
                Text.assemble(
                    (f"{role_label}: ", label_style), (wrapped, content_style)
                )
            )
            input_elements.append(Rule(style="bright_black"))

    if input_elements and isinstance(input_elements[-1], Rule):
        input_elements.pop()

    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Model Input[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()

    wrapped_response = textwrap.fill(
        response_text, width=82, subsequent_indent="           "
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


def extract_and_store_facts(
    client: genai.Client,
    user_msg: str,
    assistant_msg: str,
    entries: list[dict],
) -> list[dict]:
    """Prompts the model to extract facts from a turn and saves them to memory.

    Args:
        client: The Gemini client instance.
        user_msg: The latest message from the user.
        assistant_msg: The latest response from the assistant.
        entries: The current list of stored memory entries.

    Returns:
        The updated list of memory entries containing any newly extracted facts.

    Side effects:
        Makes a network call to the Gemini API and overwrites the memory file.
        Prints extraction logs.
    """
    extraction_prompt = f"""You are a memory extraction system.
Given a conversation turn, extract factual statements about the user as a JSON array.
Each object must have exactly two keys:
  "keywords": list of 2-5 lowercase words to use when searching for this fact
  "fact":     one concise sentence stating the fact

Conversation:
User: {user_msg}
Assistant: {assistant_msg}

Return only valid JSON with no markdown fences. Example:
[{{"keywords": ["name", "user"], "fact": "The user's name is Alex."}}]
"""
    response = client.models.generate_content(
        model=MODEL,
        contents=extraction_prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    reply = response.text.strip()
    log_llm_interaction(None, extraction_prompt, reply)

    # Clean the raw string before parsing to handle unexpected formatting
    raw = re.sub(r"^```[a-z]*\n?", "", reply)
    raw = re.sub(r"\n?```$", "", raw)

    new_facts = json.loads(raw)
    entries.extend(new_facts)
    save_memory(entries)
    return entries


# ─── Agent: No Memory ─────────────────────────────────────────────────────────


def run_no_memory_session(
    client: genai.Client, label: str, turns: list[str]
) -> list[str]:
    """Runs a multi-turn conversation session without persistent memory.

    Args:
        client: The Gemini client instance.
        label: The descriptive header printed before execution.
        turns: A list of strings representing consecutive user prompts.

    Returns:
        A list of assistant responses corresponding to each user turn.

    Side effects:
        Makes API calls and prints formatted chat logs to the terminal.
    """
    console.print(Rule(f"[bold]{label}[/bold]", style="white"))
    console.print()

    history: list[dict] = []
    responses: list[str] = []

    for i, user_msg in enumerate(turns, 1):
        contents = [
            types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
            for m in history
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))

        system_instruction = (
            "You are a helpful assistant. "
            "Answer only from what has been shared in this conversation. "
            "If you don't know something, say so clearly."
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0,
            ),
        )
        reply = response.text.strip()

        log_llm_interaction(system_instruction, contents, reply)

        console.print(f"\n[bold blue]> Turn {i}[/bold blue]")

        prefix_user = "[dim]user:[/dim]"
        wrapped_user = textwrap.fill(user_msg, width=88, subsequent_indent="         ")
        console.print(f"  {prefix_user} [blue]{wrapped_user}[/blue]")

        prefix_assistant = "[dim]assistant:[/dim]"
        wrapped_assistant = textwrap.fill(
            reply, width=88, subsequent_indent="         "
        )
        console.print(f"  {prefix_assistant} [italic]{wrapped_assistant}[/italic]")
        console.print()

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "model", "content": reply})
        responses.append(reply)

    return responses


# ─── Agent: External Memory ───────────────────────────────────────────────────


def run_memory_session(
    client: genai.Client,
    label: str,
    turns: list[str],
    write_memory: bool,
) -> list[str]:
    """Runs a session using keyword-based retrieval from an external JSON file.

    Args:
        client: The Gemini client instance.
        label: The descriptive header printed before execution.
        turns: A list of strings representing consecutive user prompts.
        write_memory: If True, extract facts from each turn and save to disk.

    Returns:
        A list of assistant responses corresponding to each user turn.

    Side effects:
        Makes API calls, reads/writes JSON files, prints formatted chat logs.
    """
    console.print(Rule(f"[bold]{label}[/bold]", style="white"))
    console.print()

    history: list[dict] = []
    responses: list[str] = []

    for i, user_msg in enumerate(turns, 1):
        all_entries = load_memory()
        relevant = retrieve_relevant(user_msg, all_entries)

        memory_block = ""
        if relevant:
            facts_list = "\n".join(f"- {e['fact']}" for e in relevant)
            memory_block = f"\n\nFacts retrieved from memory:\n{facts_list}"

        system_prompt = (
            "You are a helpful assistant."
            " Answer from the conversation history and any facts provided below."
            " If you don't know something, say so clearly."
            f"{memory_block}"
        )

        console.print(
            f"\n[bold cyan]> Turn {i}[/bold cyan] [dim]({len(relevant)} retrieved / {len(all_entries)} total in memory)[/dim]"
        )
        for e in relevant:
            console.print(f"    [dim]recall →[/dim] [yellow]{e['fact']}[/yellow]")

        contents = [
            types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
            for m in history
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
            ),
        )
        reply = response.text.strip()

        log_llm_interaction(system_prompt, contents, reply)

        prefix_user = "[dim]user:[/dim]"
        wrapped_user = textwrap.fill(user_msg, width=88, subsequent_indent="         ")
        console.print(f"  {prefix_user} [blue]{wrapped_user}[/blue]")

        prefix_assistant = "[dim]assistant:[/dim]"
        wrapped_assistant = textwrap.fill(
            reply, width=88, subsequent_indent="         "
        )
        console.print(f"  {prefix_assistant} [italic]{wrapped_assistant}[/italic]")

        if write_memory:
            updated = extract_and_store_facts(client, user_msg, reply, all_entries)
            console.print(
                f"    [dim]wrote  →[/dim] "
                f"[green]{len(updated)} total entries now in {MEMORY_FILE}[/green]"
            )

        console.print()

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "model", "content": reply})
        responses.append(reply)

    return responses


# ─── Verdict ──────────────────────────────────────────────────────────────────


def print_verdict(no_mem_responses: list[str], mem_responses: list[str]) -> None:
    """Prints a side-by-side comparison table summarizing the experiment results.

    Args:
        no_mem_responses: The list of S2 answers generated by the baseline agent.
        mem_responses: The list of S2 answers generated by the memory agent.

    Side effects:
        Prints a rich table and summary stats to the terminal.
    """
    console.print(
        Rule("[bold yellow]Verdict — Session 2 Recall[/bold yellow]", style="yellow")
    )
    console.print()

    table = Table(title="Results", show_lines=True)
    table.add_column("Question", style="bold", min_width=34)
    table.add_column("No-Memory Agent", style="red", min_width=32)
    table.add_column("Memory Agent", style="green", min_width=32)

    for q, no_mem, mem in zip(SESSION_2_TURNS, no_mem_responses, mem_responses):
        table.add_row(
            textwrap.fill(q, 32),
            textwrap.fill(no_mem[:220], 30),
            textwrap.fill(mem[:220], 30),
        )

    console.print(table)
    console.print()

    console.print(Rule("[bold yellow]Stats[/bold yellow]", style="yellow"))
    console.print()

    entries = load_memory()
    console.print(f"  [bold]Session 1 turns:[/bold]          {len(SESSION_1_TURNS)}")
    console.print(f"  [bold]Session 2 turns:[/bold]          {len(SESSION_2_TURNS)}")
    console.print(f"  [bold]Memory file:[/bold]              [dim]{MEMORY_FILE}[/dim]")
    console.print(
        f"  [bold]Facts stored after S1:[/bold]    [green]{len(entries)} entries[/green]"
    )
    console.print()
    console.print(
        f"  [bold]No-memory agent S2:[/bold]  [bold red]0 facts retained — blank slate[/bold red]"
    )
    console.print(
        f"  [bold]Memory agent S2:[/bold]      [bold green]{len(entries)} facts available — persisted via file[/bold green]"
    )
    console.print()
    console.print(
        "  [dim]Takeaway:[/dim] "
        "[bold]in-context memory is ephemeral.[/bold] "
        "External memory requires an explicit write + retrieval strategy,"
        " but it survives across sessions."
    )
    console.print()


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    """Main entry point orchestrating the memory comparison experiment.

    Runs part 1 (no memory) and part 2 (external memory) across two simulated
    sessions each, then prints the verdict comparing their retention.

    Side effects:
        Unlinks existing memory_store.json, makes API calls, orchestrates tests.
    """
    console.print(
        Panel.fit(
            "[bold yellow]Memory That Persists Across Sessions[/bold yellow]\n"
            "[dim]Ephemeral in-context memory vs. persistent external memory.[/dim]\n"
            "[dim]2 agents × 2 sessions × 3 turns each[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    console.print(Rule("[bold red]Part 1 — No-Memory Agent[/bold red]", style="red"))
    console.print(
        "[dim]  In-context history only. Each session starts with an empty messages list.[/dim]"
    )
    console.print()

    run_no_memory_session(client, "Session 1  ·  sharing facts", SESSION_1_TURNS)
    no_mem_s2 = run_no_memory_session(
        client,
        "Session 2  ·  testing recall  (new session, no history)",
        SESSION_2_TURNS,
    )

    console.print()

    console.print(
        Rule("[bold green]Part 2 — External Memory Agent[/bold green]", style="green")
    )
    console.print(
        "[dim]  Writes facts to disk after each turn (Session 1). "
        "Retrieves by keyword at each turn start.[/dim]"
    )
    console.print()

    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()

    run_memory_session(
        client,
        "Session 1  ·  sharing facts + writing memory",
        SESSION_1_TURNS,
        write_memory=True,
    )
    mem_s2 = run_memory_session(
        client,
        "Session 2  ·  new context, reads from memory file",
        SESSION_2_TURNS,
        write_memory=False,
    )

    console.print()

    print_verdict(no_mem_s2, mem_s2)


if __name__ == "__main__":
    main()
