from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Finding:
    severity: str
    description: str
    suggestion: str
    line: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        """Constructs a Finding instance from a raw dictionary.

        Uses safe defaults for missing fields, ensuring that severity
        is at least 'medium' if unspecified.
        """
        return cls(
            severity=d.get("severity", "medium"),
            description=d.get("description", ""),
            suggestion=d.get("suggestion", ""),
            line=d.get("line"),
        )

    def to_dict(self) -> dict:
        """Serializes the Finding into a dictionary format.

        This format is suitable for persistent storage or inclusion
        in subsequent LLM prompts.
        """
        return {
            "line": self.line,
            "severity": self.severity,
            "description": self.description,
            "suggestion": self.suggestion,
        }


@dataclass
class SpecialistReport:
    agent: str
    summary: str
    findings: List[Finding] = field(default_factory=list)

    @classmethod
    def from_dict(cls, agent: str, d: dict) -> "SpecialistReport":
        """Constructs a SpecialistReport from an LLM response dictionary.

        Initializes the report with a specific agent name and parses the
        list of findings into Finding objects.
        """
        # Map each raw finding dictionary to a Finding instance
        findings = [Finding.from_dict(f) for f in d.get("findings", [])]
        return cls(agent=agent, summary=d.get("summary", ""), findings=findings)

    def to_dict(self) -> dict:
        """Serializes the full report into a plain dictionary.

        Includes the summary and a list of serialized finding dictionaries.
        """
        return {
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class ReviewDecision:
    repo: str
    summary: str
    verdict: str
    findings: List[Finding] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, repo: str, d: dict) -> "ReviewDecision":
        """Constructs a final ReviewDecision from the critic's response.

        Integrates the repository context and provides a default 'comment'
        verdict if the LLM output is incomplete.
        """
        # Parse consolidated findings from the critic's output
        findings = [Finding.from_dict(f) for f in d.get("findings", [])]
        return cls(
            repo=repo,
            summary=d.get("summary", ""),
            verdict=d.get("verdict", "comment"),
            findings=findings,
            key_decisions=d.get("key_decisions", []),
        )
