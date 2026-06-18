"""
Paper ingestion.

Supports:
  - PDF (.pdf) via pypdf
  - Plain text (.txt, .md)
  - Any other extension treated as plain text

Returns a cleaned string of the paper content.
"""

from __future__ import annotations

import os


def load_paper(path: str) -> str:
    """Load a paper from `path` and return its text content."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Paper not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        return _load_pdf(path)
    else:
        return _load_text(path)


def _load_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF input.  "
            "Install with: pip install pypdf --break-system-packages"
        )

    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    raw = "\n".join(pages)
    return _clean(raw)


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return _clean(f.read())


def _clean(text: str) -> str:
    """Remove excessive whitespace while preserving paragraph structure."""
    lines = text.split("\n")
    cleaned = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = len(stripped.strip()) == 0
        if is_blank:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(stripped)
            prev_blank = False
    return "\n".join(cleaned).strip()
