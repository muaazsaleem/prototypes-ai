from dataclasses import dataclass, field
from typing import Literal

VerdictType = Literal["TRUE", "FALSE", "UNVERIFIABLE"]


@dataclass
class Claim:
    """A single atomic, independently verifiable statement extracted from a passage."""

    index: int
    text: str


@dataclass
class Evidence:
    """Supporting and contradicting evidence gathered from the model's knowledge for one claim."""

    claim: str
    supporting: list[str]  # facts that increase likelihood the claim is true
    contradicting: list[str]  # facts that increase likelihood the claim is false


@dataclass
class VoteResult:
    """Outcome of self-consistency voting across VOTING_ROUNDS independent model calls.

    confidence is the fraction of rounds that agreed on final_verdict (e.g. 4/5 = 0.8).
    individual_votes preserves the raw per-round verdicts for transparency.
    """

    claim: str
    individual_votes: list[str]  # one entry per voting round
    final_verdict: VerdictType
    confidence: float
    reasoning: str


@dataclass
class FactCheckReport:
    """Aggregated fact-check output for an entire passage.

    overall_credibility_score is the fraction of claims judged TRUE (0.0–1.0).
    """

    passage: str
    total_claims: int
    results: list[VoteResult]
    overall_credibility_score: float
