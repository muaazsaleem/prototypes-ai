import json
from collections import Counter

from google import genai
from google.genai import types

from config import MODEL_NAME, TEMPERATURE_VOTE, VOTING_ROUNDS
from models import Evidence, VoteResult

VOTE_PROMPT = """You are a fact-checking judge. Based on the claim and the evidence provided, decide whether the claim is TRUE, FALSE, or UNVERIFIABLE.

Claim:
{claim}

Supporting evidence:
{supporting}

Contradicting evidence:
{contradicting}

Verdict options:
- TRUE: The claim is factually accurate based on the evidence.
- FALSE: The claim is factually inaccurate based on the evidence.
- UNVERIFIABLE: There is insufficient evidence to determine accuracy.

Respond with a JSON object in this exact format:
{{
  "verdict": "TRUE",
  "reasoning": "One sentence explaining your verdict."
}}"""


def _single_vote(client: genai.Client, evidence: Evidence) -> tuple[str, str]:
    """Makes one independent verdict call and returns (verdict, reasoning).

    Uses TEMPERATURE_VOTE (0.8) so that repeated calls to the same claim can
    produce different verdicts — that variance is exactly what self-consistency
    voting is designed to measure.
    Falls back to UNVERIFIABLE if the model omits the verdict field.
    """
    # Render evidence lists as bullet points; signal "None found" so the model
    # doesn't hallucinate evidence when a side is genuinely empty.
    supporting_text = (
        "\n".join(f"- {e}" for e in evidence.supporting)
        if evidence.supporting
        else "- None found"
    )
    contradicting_text = (
        "\n".join(f"- {e}" for e in evidence.contradicting)
        if evidence.contradicting
        else "- None found"
    )

    prompt = VOTE_PROMPT.format(
        claim=evidence.claim,
        supporting=supporting_text,
        contradicting=contradicting_text,
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=TEMPERATURE_VOTE,
        ),
    )

    data = json.loads(response.text)
    verdict = data.get("verdict", "UNVERIFIABLE").upper()
    reasoning = data.get("reasoning", "")

    return verdict, reasoning


def vote_on_claim(client: genai.Client, evidence: Evidence) -> VoteResult:
    """Runs VOTING_ROUNDS independent verdict calls and aggregates them into a VoteResult.

    Self-consistency voting: the same claim + evidence is judged N times at high temperature.
    The majority verdict wins; confidence = winning_count / VOTING_ROUNDS.
    Stores one representative reasoning string for the winning verdict.
    """
    votes = []
    reasonings = {}

    for _ in range(VOTING_ROUNDS):
        verdict, reasoning = _single_vote(client, evidence)
        votes.append(verdict)
        # Keep one reasoning sample per verdict type for the final explanation
        if verdict not in reasonings:
            reasonings[verdict] = reasoning

    vote_counts = Counter(votes)
    final_verdict, top_count = vote_counts.most_common(1)[0]
    confidence = top_count / VOTING_ROUNDS  # fraction of rounds that agreed

    return VoteResult(
        claim=evidence.claim,
        individual_votes=votes,
        final_verdict=final_verdict,
        confidence=confidence,
        reasoning=reasonings.get(final_verdict, ""),
    )
