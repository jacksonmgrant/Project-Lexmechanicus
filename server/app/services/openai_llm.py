from __future__ import annotations
import httpx, json

from ..errors import raise_api_error
from ..config import settings


def _build_agent_instructions(system: str) -> str:
    return (
        f"You are {settings.OPENAI_AGENT_NAME}. "
        "You answer questions about tabletop rules documents and uploaded reference material. "
        "Prefer retrieved evidence over guesswork. "
        "Use relevant retrieved snippets to give the best supported answer you can, even when they are partial excerpts. "
        "Only say 'uncertain' when the retrieved evidence does not answer the user's core question or directly conflicts.\n\n"
        f"{system}"
    )


def _build_input_items(user: str, context_chunks: list[dict]) -> list[dict]:
    serialized_chunks = []
    for idx, chunk in enumerate(context_chunks):
        serialized_chunks.append(
            {
                "citation_id": f"c{idx}",
                "title": chunk.get("title"),
                "section": chunk.get("section"),
                "snippet": chunk.get("snippet"),
                "file_id": chunk.get("file_id"),
                "filename": chunk.get("filename"),
            }
        )

    context_text = json.dumps(serialized_chunks, ensure_ascii=True)[:12000]
    return [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": user},
                {
                    "type": "input_text",
                    "text": "Retrieved context JSON:\n" + context_text,
                },
            ],
        }
    ]


async def stream_completion(model: str, system: str, user: str, context_chunks: list[dict]):
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise_api_error(503, "AI responses are not configured right now.", "AI_NOT_CONFIGURED")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if settings.OPENAI_PROJECT_ID:
        headers["OpenAI-Project"] = settings.OPENAI_PROJECT_ID
    if settings.OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID
    payload: dict[str, object] = {
        "model": model,
        "instructions": _build_agent_instructions(system),
        "input": _build_input_items(user, context_chunks),
        "stream": True,
        "max_output_tokens": 320,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
    }
    try:
        async with httpx.AsyncClient(timeout=None) as client:
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
                            yield delta
                    elif event_type == "response.incomplete":
                        details = event.get("response", {}).get("incomplete_details") or {}
                        reason = details.get("reason")
                        if reason == "max_output_tokens":
                            raise_api_error(502, "The AI response ran out of output tokens before it could finish. Please try again.", "AI_RESPONSE_INCOMPLETE")
                        raise_api_error(502, "The AI response ended before completion. Please try again.", "AI_RESPONSE_INCOMPLETE")
                    elif event_type == "error":
                        message = event.get("message") or "OpenAI streaming error"
                        raise_api_error(502, message, "AI_STREAM_ERROR")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise_api_error(503, "AI responses are unavailable because the provider credentials are invalid.", "AI_AUTH_FAILED")
        if e.response.status_code == 429:
            raise_api_error(503, "The AI provider is rate limiting requests right now. Please try again shortly.", "AI_RATE_LIMITED")
        raise_api_error(502, "The AI provider returned an error while generating a response.", "AI_PROVIDER_ERROR")
    except httpx.HTTPError:
        raise_api_error(503, "The AI provider could not be reached. Please try again.", "AI_PROVIDER_UNAVAILABLE")
