from __future__ import annotations
from hashlib import blake2b


def cite_id(file_id: int, start_byte: int, end_byte: int) -> str:
    return blake2b(f"{file_id}:{start_byte}:{end_byte}".encode(), digest_size=10).hexdigest()


# Convert model text with placeholders like [[c0]] to linked citations.


def inject_citations(answer: str, citations: list[dict]) -> str:
    for i, c in enumerate(citations):
        anchor = f"[[c{i}]]"
        url = f"/viewer/{c['file_id']}?start={c['start_byte']}&end={c['end_byte']}"
        link = f"<a href=\"{url}\" class=\"citation\">[{i+1}]</a>"
        answer = answer.replace(anchor, link)
    return answer