from __future__ import annotations
from io import BytesIO

from markdown_it import MarkdownIt
from pypdf import PdfReader


md = MarkdownIt()


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_text_from_markdown(data: bytes) -> str:
    # Convert markdown to plain text by stripping tokens.
    tokens = md.parse(data.decode("utf-8", errors="ignore"))
    out: list[str] = []
    for t in tokens:
        if t.type == "inline" and t.content:
            out.append(t.content)
    return "\n".join(out)


def normalize_text(mime: str, data: bytes) -> str:
    if mime in ("application/pdf",):
        return extract_text_from_pdf(data)
    if mime in ("text/markdown", "text/x-markdown", "text/plain"):
        return extract_text_from_markdown(data) if mime != "text/plain" else data.decode("utf-8", errors="ignore")
    # Unknown types: best-effort raw decode.
    return data.decode("utf-8", errors="ignore")
