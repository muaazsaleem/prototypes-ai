import json

from google import genai
from google.genai import types

from config import MODEL_NAME, TEMPERATURE_DECOMPOSE
from models import Claim

DECOMPOSE_PROMPT = """You are a fact-checking assistant. Your task is to decompose the given passage into atomic, independently verifiable claims.

Rules:
- Each claim must be a single, standalone factual statement.
- Do not combine multiple facts into one claim.
- Do not include opinions or subjective statements.
- Extract only claims that can be verified as TRUE or FALSE.

Passage:
{passage}

Respond with a JSON object in this exact format:
{{
  "claims": [
    "claim text 1",
    "claim text 2"
  ]
}}"""


def decompose_passage(client: genai.Client, passage: str) -> list[Claim]:
    """Splits a passage into a list of atomic, independently verifiable claims.

    Makes a single LLM call with response_mime_type="application/json" so the model
    returns structured output without needing manual JSON extraction from prose.
    Returns an empty list if the model produces no claims.
    """
    prompt = DECOMPOSE_PROMPT.format(passage=passage)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=TEMPERATURE_DECOMPOSE,
        ),
    )

    data = json.loads(response.text)
    claims = data.get("claims", [])

    # index is 1-based so claim numbers match human-readable display
    return [Claim(index=i, text=c.strip()) for i, c in enumerate(claims, start=1)]
