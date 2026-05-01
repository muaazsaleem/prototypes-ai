import json

from google import genai
from google.genai import types

from config import MODEL_NAME, TEMPERATURE_EVIDENCE
from models import Evidence

EVIDENCE_PROMPT = """You are a fact-checking researcher. For the given claim, recall what you know and provide evidence both supporting and contradicting it.

Claim:
{claim}

Instructions:
- List up to 3 pieces of supporting evidence (facts that make this claim more likely to be true).
- List up to 3 pieces of contradicting evidence (facts that make this claim more likely to be false).
- Be concise — one sentence per evidence item.
- If you have no evidence for a side, return an empty list.

Respond with a JSON object in this exact format:
{{
  "supporting": ["evidence 1", "evidence 2"],
  "contradicting": ["evidence 1", "evidence 2"]
}}"""


def gather_evidence(client: genai.Client, claim: str) -> Evidence:
    """Asks the model to recall supporting and contradicting evidence for a single claim.

    Evidence comes from the model's parametric knowledge — no web search or external tools.
    Returns an Evidence object; either list may be empty if the model finds nothing for that side.
    """
    prompt = EVIDENCE_PROMPT.format(claim=claim)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=TEMPERATURE_EVIDENCE,
        ),
    )

    data = json.loads(response.text)

    return Evidence(
        claim=claim,
        supporting=data.get("supporting", []),
        contradicting=data.get("contradicting", []),
    )
