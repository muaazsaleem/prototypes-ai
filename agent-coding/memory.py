import json


class WorkingMemory:
    """Tracks the agent's progress, including modified files and reflections.

    This state is injected into subsequent prompts to provide context and
    prevent the agent from repeating previous mistakes.
    """

    def __init__(self):
        """Initialises empty memory with zero attempts and empty lists for tracking."""
        self.attempts = 0
        self.read_files = set()
        self.modified_files = set()
        self.reflections = []

    def mark_read(self, path: str):
        """Adds a file path to the set of files read by the agent."""
        if path:
            self.read_files.add(path)

    def mark_modified(self, path: str):
        """Adds a file path to the set of files modified by the agent."""
        if path:
            self.modified_files.add(path)

    def add_reflection(self, reflection: str):
        """Stores a reflection text from a failed attempt."""
        self.reflections.append(reflection)

    def format_for_prompt(self) -> str:
        """Returns a string representation of the current memory for LLM prompts.

        Includes current attempt count, files read, files modified, and
        all past reflections.
        """
        return json.dumps(
            {
                "attempts_so_far": self.attempts,
                "files_read": list(self.read_files),
                "files_modified": list(self.modified_files),
                "past_reflections": self.reflections,
            },
            indent=2,
        )
