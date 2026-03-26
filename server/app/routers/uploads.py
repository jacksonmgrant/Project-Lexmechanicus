from __future__ import annotations

import os

import aioboto3
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import delete, insert, select, text, update

from ..auth import get_current_user, get_optional_user
from ..db import SessionLocal
from ..models import File as FileModel, FileChunk, Folder
from ..services.chunker import iter_chunks
from ..services.embeddings import embed_texts
from ..services.openai_vector_store import OpenAIVectorStoreSyncError, sync_file_to_vector_store
from ..services.parsers import normalize_text
from ..config import settings


router = APIRouter(prefix="/uploads", tags=["uploads"])


S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_USE_SSL = bool(int(os.getenv("S3_USE_SSL", "0")))


LIST_FILES_SQL = """
SELECT
    f.id,
    f.filename,
    f.mime_type,
    f.size_bytes,
    f.is_public,
    f.openai_vector_store_status,
    fo.id AS folder_id,
    fo.game_system_id,
    u.email AS uploader_email,
    COALESCE(fc.chunk_count, 0) AS chunk_count
FROM files f
JOIN folders fo ON fo.id = f.folder_id
JOIN users u ON u.id = fo.user_id
LEFT JOIN (
    SELECT file_id, COUNT(*)::int AS chunk_count
    FROM file_chunks
    GROUP BY file_id
) fc ON fc.file_id = f.id
WHERE
    (
        (
            :scope = 'browse' AND (
                f.is_public = TRUE
                OR (:user_id IS NOT NULL AND fo.user_id = :user_id)
            )
        )
        OR (
            :scope = 'mine' AND :user_id IS NOT NULL AND fo.user_id = :user_id
        )
    )
    AND (:game_system_id IS NULL OR fo.game_system_id = :game_system_id)
    AND (
        :q = ''
        OR LOWER(f.filename) LIKE '%' || LOWER(:q) || '%'
        OR LOWER(u.email) LIKE '%' || LOWER(:q) || '%'
        OR CAST(f.id AS TEXT) = :q
    )
ORDER BY f.id DESC
LIMIT :limit
"""


@router.post("/")
async def upload_file(
    folder_id: int = Form(...),
    is_public: bool = Form(False),
    f: UploadFile = File(...),
    user=Depends(get_current_user),
):
    # PUBLIC SHARING REQUIRES RIGHTS OWNERSHIP. Uploader must certify rights.
    if is_public:
        # TODO: add rights checkbox validation and content fingerprinting to detect publisher-origin files.
        pass

    if not S3_BUCKET:
        raise HTTPException(status_code=500, detail="S3_BUCKET is not configured")

    data = await f.read()
    key = f"u/{user.id}/folders/{folder_id}/{f.filename}"

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        use_ssl=S3_USE_SSL,
    ) as s3:
        await s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=f.content_type or "application/octet-stream",
        )

    async with SessionLocal() as db:
        res = await db.execute(
            insert(FileModel)
            .values(
                {
                    "folder_id": folder_id,
                    "filename": f.filename,
                    "mime_type": f.content_type or "application/octet-stream",
                    "size_bytes": len(data),
                    "s3_key": key,
                    "is_public": bool(is_public),
                }
            )
            .returning(FileModel.id)
        )
        file_id = res.scalar_one()

        openai_sync_status = None
        if settings.OPENAI_VECTOR_STORE_ID and settings.OPENAI_VECTOR_STORE_AUTO_SYNC:
            try:
                sync_result = await sync_file_to_vector_store(
                    filename=f.filename,
                    mime_type=f.content_type or "application/octet-stream",
                    data=data,
                    vector_store_id=settings.OPENAI_VECTOR_STORE_ID,
                    attributes={
                        "app_file_id": file_id,
                        "folder_id": folder_id,
                        "user_id": user.id,
                        "filename": f.filename,
                        "source": "lexmechanicus_upload",
                    },
                )
                openai_sync_status = sync_result["openai_vector_store_status"] or "in_progress"
                await db.execute(
                    update(FileModel)
                    .where(FileModel.id == file_id)
                    .values(
                        {
                            "openai_file_id": sync_result["openai_file_id"],
                            "openai_vector_store_file_id": sync_result["openai_vector_store_file_id"],
                            "openai_vector_store_status": sync_result["openai_vector_store_status"],
                            "openai_last_error": None,
                        }
                    )
                )
            except (OpenAIVectorStoreSyncError, httpx.HTTPError) as exc:
                openai_sync_status = "failed"
                await db.execute(
                    update(FileModel)
                    .where(FileModel.id == file_id)
                    .values(
                        {
                            "openai_vector_store_status": "failed",
                            "openai_last_error": str(exc)[:2000],
                        }
                    )
                )

        # Ingest synchronously for simplicity; move to a background worker for scale.
        text = normalize_text(f.content_type or "application/octet-stream", data)
        chunks = list(iter_chunks(text))
        embeddings = await embed_texts([c["snippet"] for c in chunks]) if chunks else []
        for c, emb in zip(chunks, embeddings):
            await db.execute(
                insert(FileChunk).values(
                    {
                        "file_id": file_id,
                        "start_byte": c["start_byte"],
                        "end_byte": c["end_byte"],
                        "title": c["title"],
                        "section": c["section"],
                        "snippet": c["snippet"],
                        "embedding": emb,
                    }
                )
            )
        await db.commit()

    return {
        "status": "ok",
        "file_id": file_id,
        "chunks": len(chunks),
        "openai_vector_store_status": openai_sync_status,
    }


@router.get("/files")
async def list_files(
    scope: str = Query("browse", pattern="^(browse|mine)$"),
    q: str = Query("", max_length=200),
    game_system_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_optional_user),
):
    if scope == "mine" and user is None:
        raise HTTPException(status_code=401, detail="Create an account or sign in to use this feature.")

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(LIST_FILES_SQL),
                {
                    "scope": scope,
                    "user_id": user.id if user else None,
                    "game_system_id": game_system_id,
                    "q": q.strip(),
                    "limit": limit,
                },
            )
        ).mappings().all()

    return [
        {
            "id": row["id"],
            "title": row["filename"],
            "filename": row["filename"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "is_public": row["is_public"],
            "status": row["openai_vector_store_status"] or "ready",
            "folder_id": row["folder_id"],
            "game_system_id": row["game_system_id"],
            "uploader_email": row["uploader_email"],
            "chunk_count": row["chunk_count"],
            # The current schema does not persist view/download timestamps, so the UI
            # receives stable placeholders until those analytics fields exist.
            "downloads": 0,
            "views": 0,
        }
        for row in rows
    ]


@router.delete("/{file_id}")
async def delete_file(file_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        file_row = await db.execute(
            select(FileModel, Folder.user_id)
            .join(Folder, Folder.id == FileModel.folder_id)
            .where(FileModel.id == file_id)
        )
        record = file_row.first()
        if not record:
            raise HTTPException(status_code=404, detail="File not found.")

        file_model, owner_id = record
        if owner_id != user.id:
            raise HTTPException(status_code=403, detail="You do not have permission to delete this file.")

        if S3_BUCKET:
            session = aioboto3.Session()
            async with session.client(
                "s3",
                endpoint_url=S3_ENDPOINT,
                region_name=S3_REGION,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                use_ssl=S3_USE_SSL,
            ) as s3:
                try:
                    await s3.delete_object(Bucket=S3_BUCKET, Key=file_model.s3_key)
                except Exception:
                    pass

        await db.execute(delete(FileModel).where(FileModel.id == file_id))
        await db.commit()

    return {"status": "ok"}
