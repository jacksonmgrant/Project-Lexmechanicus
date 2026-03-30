from __future__ import annotations
import json
import httpx

from ..errors import raise_api_error
from ..config import settings


PRIMARY_MAX_OUTPUT_TOKENS = 720
RETRY_MAX_OUTPUT_TOKENS = 1100


def _build_agent_instructions(system: str) -> str:
    return (
        f"You are {settings.OPENAI_AGENT_NAME}. "
        "You answer tabletop rules questions using only the retrieved excerpts. "
        "Act like a careful rules judge: give the ruling first, then the controlling rule explanation immediately after it. "
        "Lead with the operative rule, not background, theme text, or tangential related rules. "
        "Prefer a decisive paraphrase over hedging when the evidence is clear. "
        "If the evidence supports only part of the answer, state the supported part and identify the missing condition. "
        "If multiple excerpts matter, synthesize the controlling rule and its exception together instead of discussing them separately. "
        "Use the recent conversation only to resolve what the current question is referring to; do not drift into answering earlier questions unless the current question asks for that. "
        "When quoting matters, use only short exact quotes taken from the provided 'Key quote' or 'Supporting quote' lines. Never invent, merge, or clean up a quote beyond whitespace normalization. "
        "If a limitation or exception changes the ruling, mention it immediately after the ruling instead of saving it for the end. "
        "Avoid preambles like 'Based on the excerpts' or references to JSON, retrieval, or internal context. "
        "Use inline citation placeholders like [[c0]] after each supported sentence or bullet. "
        "Only say 'uncertain' when the retrieved evidence does not support a ruling or directly conflicts.\n\n"
        f"{system}"
    )


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _trim_context_excerpt(value: str, *, max_chars: int = 420) -> str:
    normalized = _clean_text(value)
    if len(normalized) <= max_chars:
        return normalized
    truncated = normalized[: max_chars - 3].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "..."


def _append_chunk_lines(lines: list[str], index: int, chunk: dict) -> None:
    source_title = _clean_text(chunk.get("source_title") or chunk.get("title") or chunk.get("file_title") or chunk.get("filename") or f"Document {index + 1}")
    section = _clean_text(chunk.get("section"))
    excerpt = _trim_context_excerpt(chunk.get("excerpt") or chunk.get("snippet") or "")
    key_quote = _clean_text(chunk.get("key_quote"))
    supporting_quote = _clean_text(chunk.get("supporting_quote"))

    lines.append(f"[c{index}] Source: {source_title}")
    if section and section.lower() != source_title.lower():
        lines.append(f"Section: {section}")
    if key_quote:
        lines.append(f'Key quote: "{key_quote}"')
    if supporting_quote and supporting_quote.lower() != key_quote.lower():
        lines.append(f'Supporting quote: "{supporting_quote}"')
    if excerpt:
        lines.append(f"Context excerpt: {excerpt}")
    lines.append("")


def _append_conversation_lines(lines: list[str], conversation_history: list[dict]) -> None:
    if not conversation_history:
        return

    lines.append("Recent conversation:")
    for turn in conversation_history[-6:]:
        role = _clean_text(turn.get("role") or "").lower()
        content = _trim_context_excerpt(str(turn.get("content") or ""), max_chars=260)
        if role not in {"user", "assistant"} or not content:
            continue
        prefix = "User" if role == "user" else "Assistant"
        lines.append(f"{prefix}: {content}")
    lines.append("")


def _build_context_brief(
    user: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
    *,
    max_chars: int = 16000,
) -> str:
    lines = [
        "User question:",
        _clean_text(user),
        "",
    ]
    _append_conversation_lines(lines, conversation_history or [])
    lines.append("Primary evidence (highest-confidence rule matches):")

    if not context_chunks:
        lines.append("No supporting excerpts were retrieved.")
    else:
        primary_chunks = context_chunks[:2]
        supporting_chunks = context_chunks[2:6]

        for idx, chunk in enumerate(primary_chunks):
            _append_chunk_lines(lines, idx, chunk)

        if supporting_chunks:
            lines.append("Supporting evidence / exceptions:")
            lines.append("")
            for offset, chunk in enumerate(supporting_chunks, start=len(primary_chunks)):
                _append_chunk_lines(lines, offset, chunk)

    lines.extend(
        [
            "Answer expectations:",
            "- First sentence: the direct ruling or answer to the question.",
            "- Second sentence: the controlling rule explanation, using the strongest evidence first.",
            "- Third sentence: the most relevant exception, limitation, or edge condition, only if needed.",
            "- Use plain English, but include one short exact quote when it materially strengthens the answer.",
            "- Quote only from lines labeled 'Key quote' or 'Supporting quote'.",
            "- Do not lead with background, examples, or adjacent rules before the controlling rule.",
            "- Cite each supported sentence or bullet with [[c#]].",
            "- Reply with exactly 'uncertain' only if the excerpts do not support a ruling.",
        ]
    )

    brief = "\n".join(lines).strip()
    return brief[:max_chars]


def _build_input_items(
    user: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": _build_context_brief(user, context_chunks, conversation_history),
                },
            ],
        }
    ]


def _build_payload(
    model: str,
    system: str,
    user: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
    *,
    max_output_tokens: int,
) -> dict[str, object]:
    return {
        "model": model,
        "instructions": _build_agent_instructions(system),
        "input": _build_input_items(user, context_chunks, conversation_history),
        "stream": True,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
    }


async def stream_completion(
    model: str,
    system: str,
    user: str,
    context_chunks: list[dict],
    *,
    conversation_history: list[dict] | None = None,
):
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise_api_error(503, "AI responses are not configured right now.", "AI_NOT_CONFIGURED")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if settings.OPENAI_PROJECT_ID:
        headers["OpenAI-Project"] = settings.OPENAI_PROJECT_ID
    if settings.OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID
    attempts = (
        PRIMARY_MAX_OUTPUT_TOKENS,
        RETRY_MAX_OUTPUT_TOKENS,
    )
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            for attempt_index, max_output_tokens in enumerate(attempts):
                emitted_in_attempt = False
                retry_requested = False
                payload = _build_payload(
                    model,
                    system,
                    user,
                    context_chunks,
                    conversation_history,
                    max_output_tokens=max_output_tokens,
                )
                async with client.stream("POST", "https://api.openai.com/v1/responses", headers=headers, json=payload) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            event = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta")
                            if delta:
                                emitted_in_attempt = True
                                yield delta
                        elif event_type == "response.incomplete":
                            details = event.get("response", {}).get("incomplete_details") or {}
                            reason = details.get("reason")
                            if reason == "max_output_tokens":
                                if emitted_in_attempt:
                                    return
                                if attempt_index < len(attempts) - 1:
                                    retry_requested = True
                                    break
                                raise_api_error(502, "The AI response ran out of output tokens before it could finish. Please try again.", "AI_RESPONSE_INCOMPLETE")
                            raise_api_error(502, "The AI response ended before completion. Please try again.", "AI_RESPONSE_INCOMPLETE")
                        elif event_type == "error":
                            message = event.get("message") or "OpenAI streaming error"
                            raise_api_error(502, message, "AI_STREAM_ERROR")
                if not retry_requested:
                    return
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise_api_error(503, "AI responses are unavailable because the provider credentials are invalid.", "AI_AUTH_FAILED")
        if e.response.status_code == 429:
            raise_api_error(503, "The AI provider is rate limiting requests right now. Please try again shortly.", "AI_RATE_LIMITED")
        raise_api_error(502, "The AI provider returned an error while generating a response.", "AI_PROVIDER_ERROR")
    except httpx.HTTPError:
        raise_api_error(503, "The AI provider could not be reached. Please try again.", "AI_PROVIDER_UNAVAILABLE")
