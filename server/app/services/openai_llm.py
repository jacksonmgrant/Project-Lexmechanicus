from __future__ import annotations
import httpx, json
from fastapi import HTTPException
from ..config import settings


def _build_agent_instructions(system: str) -> str:
    return (
        f"You are {settings.OPENAI_AGENT_NAME}. "
        "You answer questions about tabletop rules documents and uploaded reference material. "
        "Prefer retrieved evidence over guesswork. "
        "If the evidence is incomplete or conflicting, say 'uncertain'.\n\n"
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
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is required")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, object] = {
        "model": model,
        "instructions": _build_agent_instructions(system),
        "input": _build_input_items(user, context_chunks),
        "stream": True,
        "max_output_tokens": 220,
    }
    if settings.OPENAI_VECTOR_STORE_ID:
        payload["tools"] = [
            {
                "type": "file_search",
                "vector_store_ids": [settings.OPENAI_VECTOR_STORE_ID],
                "max_num_results": 4,
            }
        ]
        payload["tool_choice"] = "auto"
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
                    elif event_type == "error":
                        message = event.get("message") or "OpenAI streaming error"
                        raise HTTPException(status_code=502, detail=message)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
