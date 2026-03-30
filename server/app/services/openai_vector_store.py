from __future__ import annotations

import httpx

from ..config import settings


class OpenAIVectorStoreSyncError(Exception):
    pass


def _auth_headers(*, beta: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    if settings.OPENAI_PROJECT_ID:
        headers["OpenAI-Project"] = settings.OPENAI_PROJECT_ID
    if settings.OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID
    if beta:
        headers["OpenAI-Beta"] = "assistants=v2"
    return headers


async def upload_file_to_openai(filename: str, mime_type: str, data: bytes) -> str:
    if not settings.OPENAI_API_KEY:
        raise OpenAIVectorStoreSyncError("OPENAI_API_KEY is required for vector store sync")

    files = {"file": (filename, data, mime_type or "application/octet-stream")}
    form = {"purpose": "user_data"}

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.openai.com/v1/files",
            headers=_auth_headers(),
            data=form,
            files=files,
        )
        response.raise_for_status()
        payload = response.json()

    file_id = payload.get("id")
    if not file_id:
        raise OpenAIVectorStoreSyncError("OpenAI file upload did not return a file id")
    return file_id


async def attach_file_to_vector_store(
    *,
    vector_store_id: str,
    openai_file_id: str,
    attributes: dict[str, str | int | bool],
) -> dict[str, str | None]:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"https://api.openai.com/v1/vector_stores/{vector_store_id}/files",
            headers={**_auth_headers(beta=True), "Content-Type": "application/json"},
            json={"file_id": openai_file_id, "attributes": attributes},
        )
        response.raise_for_status()
        payload = response.json()

    return {
        "vector_store_file_id": payload.get("id"),
        "status": payload.get("status"),
    }


async def delete_vector_store_file(*, vector_store_id: str, vector_store_file_id: str) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.delete(
            f"https://api.openai.com/v1/vector_stores/{vector_store_id}/files/{vector_store_file_id}",
            headers=_auth_headers(beta=True),
        )
        response.raise_for_status()


async def delete_openai_file(*, openai_file_id: str) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.delete(
            f"https://api.openai.com/v1/files/{openai_file_id}",
            headers=_auth_headers(),
        )
        response.raise_for_status()


async def sync_file_to_vector_store(
    *,
    filename: str,
    mime_type: str,
    data: bytes,
    vector_store_id: str,
    attributes: dict[str, str | int | bool],
) -> dict[str, str | None]:
    openai_file_id = await upload_file_to_openai(filename, mime_type, data)
    vector_store_file = await attach_file_to_vector_store(
        vector_store_id=vector_store_id,
        openai_file_id=openai_file_id,
        attributes=attributes,
    )
    return {
        "openai_file_id": openai_file_id,
        "openai_vector_store_file_id": vector_store_file["vector_store_file_id"],
        "openai_vector_store_status": vector_store_file["status"],
    }


async def purge_file_from_vector_store(
    *,
    vector_store_id: str | None,
    openai_file_id: str | None,
    vector_store_file_id: str | None,
) -> None:
    if vector_store_id and vector_store_file_id:
        await delete_vector_store_file(
            vector_store_id=vector_store_id,
            vector_store_file_id=vector_store_file_id,
        )
    if openai_file_id:
        await delete_openai_file(openai_file_id=openai_file_id)
