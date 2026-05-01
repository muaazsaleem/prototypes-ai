import json
from typing import Dict, List

from pypdf import PdfReader

from config import GEMINI_MODEL


def load_pdf(pdf_path: str) -> str:
    """Read every page of a PDF and return the full text as a single string.

    Pages are joined with double newlines. Blank or unextractable pages are
    silently skipped (pypdf returns None for scanned images without OCR).
    """
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:  # skip pages with no extractable text
            pages.append(text.strip())
    return "\n\n".join(pages)


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict]:
    """Split text into overlapping fixed-size chunks for RAG indexing.

    Each chunk is a dict with an "id" (e.g. "chunk_0") and "text" field.
    Overlap ensures that sentences spanning a chunk boundary are present in
    both neighbours, reducing the chance of cutting a key passage in half.
    """
    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({"id": f"chunk_{idx}", "text": text[start:end]})
        idx += 1
        start += chunk_size - overlap  # slide forward by (size - overlap)

    return chunks


def extract_paper_metadata(text: str, client) -> Dict:
    """Use Gemini to extract the title, abstract summary, and method name from a paper.

    Only the first 3000 characters are sent — enough to cover the title, authors,
    and abstract for almost all papers. Returns a safe fallback dict if the LLM
    response cannot be parsed as JSON.
    """
    prompt = (
        "Extract three things from this academic paper:\n"
        "1. Full paper title\n"
        "2. One-sentence summary of the abstract\n"
        "3. The name of the main algorithm or method introduced\n\n"
        'Reply ONLY as valid JSON: {"title": "...", "abstract": "...", "method": "..."}\n\n'
        f"Paper text (first 3000 chars):\n{text[:3000]}"
    )

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)

    try:
        raw = response.text.strip()
        # Strip markdown code fences that the model sometimes wraps JSON in
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception:
        # Proceed gracefully rather than crashing the whole pipeline
        return {"title": "Unknown Paper", "abstract": "", "method": "core algorithm"}
