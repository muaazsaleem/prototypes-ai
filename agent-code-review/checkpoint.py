import hashlib
import json
from pathlib import Path
from typing import Optional

CHECKPOINT_DIR = Path("checkpoints")


def get_review_id(repo: str, diff: str) -> str:
    """Returns a short deterministic ID for a (repo, diff) pair.

    Uses the first 12 hex chars of SHA-256 to ensure collisions are unlikely
    while keeping the ID manageable for file paths and logging.
    """
    content = f"{repo}:{diff}"
    # Generate a SHA-256 hash of the concatenated repo and diff content
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def save_checkpoint(review_id: str, agent: str, data: dict) -> None:
    """Persists a specialist agent's result to disk.

    Saves the JSON data to checkpoints/<review_id>/<agent>.json. Creates
    all parent directories if they do not already exist.
    """
    run_dir = CHECKPOINT_DIR / review_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Write the serialized agent data to a JSON file named after the agent
    (run_dir / f"{agent}.json").write_text(json.dumps(data, indent=2))


def load_checkpoint(review_id: str, agent: str) -> Optional[dict]:
    """Returns the saved result for an agent if it exists, otherwise None.

    Checks the filesystem for a corresponding checkpoint file and returns
    the parsed JSON dictionary if found.
    """
    path = CHECKPOINT_DIR / review_id / f"{agent}.json"
    if path.exists():
        # Load and parse the existing checkpoint file
        return json.loads(path.read_text())
    return None
