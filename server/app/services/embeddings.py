from __future__ import annotations

import httpx

from ..config import settings


EMBEDDING_DIM = 1024


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    model = settings.EMBEDDINGS_MODEL
    payload: dict[str, object] = {"model": model, "input": texts}
    if model.startswith("text-embedding-3"):
        payload["dimensions"] = EMBEDDING_DIM

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return [d["embedding"] for d in data["data"]]
    except (httpx.HTTPError, KeyError, TypeError):
        return [[0.0] * EMBEDDING_DIM for _ in texts]
