import json
from pathlib import Path
from typing import List

MEMORY_DIR = Path("memory")
MAX_DECISIONS = 5


def load_repo_memory(repo: str) -> List[dict]:
    """Loads the stored review history for a repository from disk.

    Reads the repository-specific memory JSON file and returns a list of past
    review decisions. Returns an empty list if no memory file exists.
    """
    path = MEMORY_DIR / f"{repo}.json"
    if not path.exists():
        # No history available for this repo yet
        return []
    return json.loads(path.read_text())


def save_review_decision(repo: str, decision_data: dict) -> None:
    """Appends a review decision to the repo's memory file.

    Maintains a rolling window of the last MAX_DECISIONS entries to prevent
    unbounded file growth. Creates the memory directory if missing.
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    decisions = load_repo_memory(repo)
    decisions.append(decision_data)
    # Keep only the most recent decisions based on the MAX_DECISIONS limit
    decisions = decisions[-MAX_DECISIONS:]
    (MEMORY_DIR / f"{repo}.json").write_text(json.dumps(decisions, indent=2))


def format_memory_context(decisions: List[dict]) -> str:
    """Formats past review decisions for injection into LLM prompts.

    Converts the list of decision dictionaries into a structured string that
    the critic agent can use to maintain consistency across reviews.
    """
    if not decisions:
        # Provide a default message if no history is found
        return "No previous reviews for this repository."

    lines = [f"Past {len(decisions)} review(s) for this repository:"]
    for i, d in enumerate(decisions, 1):
        lines.append(f"\nReview {i} — verdict: {d.get('verdict', 'unknown')}")
        for kd in d.get("key_decisions", []):
            # List every key decision associated with the historical review
            lines.append(f"  - {kd}")
    return "\n".join(lines)
