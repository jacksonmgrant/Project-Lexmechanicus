from __future__ import annotations

import re


FOLLOW_UP_PATTERNS = (
    re.compile(r"^(what about|how about|what if|how does that|how do they|does that|does this|is that|is this)\b", re.IGNORECASE),
    re.compile(r"^(and|also|so|then|but)\b", re.IGNORECASE),
    re.compile(r"^(why|how|when|where)\??$", re.IGNORECASE),
)


REFERENCE_TERMS = {
    "it",
    "its",
    "that",
    "this",
    "they",
    "them",
    "their",
    "those",
    "these",
    "there",
    "one",
    "ones",
}


def _strip_citations(text: str) -> str:
    return re.sub(r"\[\[c\d+\]\]", "", text or "")


def _normalize_text(text: str, *, max_chars: int) -> str:
    normalized = " ".join(_strip_citations(text).split()).strip()
    normalized = re.sub(r"\s+([.,!?;:])", r"\1", normalized)
    if len(normalized) <= max_chars:
        return normalized
    truncated = normalized[: max_chars - 3].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "..."


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+/-]*", text.lower())


def sanitize_chat_history(history: list[dict] | None, *, max_messages: int = 6) -> list[dict]:
    sanitized: list[dict] = []
    for item in history or []:
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = _normalize_text(str(item.get("content") or ""), max_chars=420 if role == "user" else 360)
        if not content:
            continue
        sanitized.append({"role": role, "content": content})
    return sanitized[-max_messages:]


def _first_sentence(text: str) -> str:
    normalized = _normalize_text(text, max_chars=220)
    if not normalized:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return parts[0].strip() if parts else normalized


def _is_context_dependent(question: str) -> bool:
    normalized = " ".join(question.split()).strip()
    lowered = normalized.lower()
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in FOLLOW_UP_PATTERNS):
        return True
    tokens = _tokenize(lowered)
    if len(tokens) <= 3:
        return True
    if any(token in REFERENCE_TERMS for token in tokens[:4]):
        return True
    return False


def build_contextual_question(question: str, history: list[dict] | None) -> str:
    normalized_question = " ".join(question.split()).strip()
    if not normalized_question:
        return ""

    sanitized_history = sanitize_chat_history(history)
    if not sanitized_history or not _is_context_dependent(normalized_question):
        return normalized_question

    previous_user_messages = [item["content"] for item in sanitized_history if item["role"] == "user"]
    previous_assistant_messages = [item["content"] for item in sanitized_history if item["role"] == "assistant"]

    context_parts: list[str] = []
    if previous_user_messages:
        context_parts.append(previous_user_messages[-1])
        if len(previous_user_messages) > 1 and len(_tokenize(normalized_question)) <= 4:
            context_parts.append(previous_user_messages[-2])
    if previous_assistant_messages and len(_tokenize(normalized_question)) <= 5:
        context_parts.append(_first_sentence(previous_assistant_messages[-1]))

    combined_parts = [part for part in context_parts if part]
    combined_parts.append(normalized_question)
    combined = " ".join(combined_parts).strip()
    return combined[:900]
