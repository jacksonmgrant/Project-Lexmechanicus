from __future__ import annotations
from typing import Iterable


# Token-light chunking: approx 4 chars per token. Aim for ~450 tokens => ~1800 chars
CHARS_PER_CHUNK = 1800
OVERLAP = 200


def iter_chunks(text: str):
    n = len(text)
    i = 0
    while i < n:
        j = min(n, i + CHARS_PER_CHUNK)
        snippet = text[i:j]
        yield {
            "start_byte": i,
            "end_byte": j,
            "title": None,
            "section": None,
            "snippet": snippet,
        }
        if j == n:
            break
        i = max(i + CHARS_PER_CHUNK - OVERLAP, j)