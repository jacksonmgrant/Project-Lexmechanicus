from __future__ import annotations

import os
from io import BytesIO

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError
from pypdf import PdfReader
from sqlalchemy import select

from ..config import _env_bool
from ..db import SessionLocal
from ..models import File
from .parsers import extract_document_title, should_replace_with_extracted_title


S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_USE_SSL = _env_bool("S3_USE_SSL", False)


async def _read_file_bytes(key: str) -> bytes:
    if not S3_BUCKET:
        raise RuntimeError("Storage bucket is not configured.")

    session = aioboto3.Session()
    try:
        async with session.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            use_ssl=S3_USE_SSL,
        ) as s3:
            obj = await s3.get_object(Bucket=S3_BUCKET, Key=key)
            return await obj["Body"].read()
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError("Unable to load citation source file.") from exc


def _build_pdf_page_spans(data: bytes) -> list[tuple[int, int, int]]:
    reader = PdfReader(BytesIO(data))
    spans: list[tuple[int, int, int]] = []
    offset = 0
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        start = offset
        end = offset + len(text)
        spans.append((start, end, index))
        offset = end + 1
    return spans


def _resolve_page_number(start_byte: int, end_byte: int, spans: list[tuple[int, int, int]]) -> int | None:
    if not spans:
        return None

    midpoint = start_byte + max(end_byte - start_byte, 0) // 2
    for start, end, page_number in spans:
        if start <= midpoint <= max(end, start):
            return page_number
    return spans[-1][2]


async def build_chat_citations(chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []

    file_ids = sorted({int(chunk["file_id"]) for chunk in chunks if chunk.get("file_id")})
    async with SessionLocal() as db:
        rows = await db.execute(
            select(File.id, File.title, File.filename, File.mime_type, File.s3_key).where(File.id.in_(file_ids))
        )
        file_rows = rows.all()

    files_by_id = {
        file_id: {
            "title": title or filename or f"Document {file_id}",
            "filename": filename,
            "mime_type": mime_type,
            "s3_key": s3_key,
        }
        for file_id, title, filename, mime_type, s3_key in file_rows
    }
    file_bytes_by_file_id: dict[int, bytes] = {}
    page_spans_by_file_id: dict[int, list[tuple[int, int, int]]] = {}

    citations: list[dict] = []
    for index, chunk in enumerate(chunks):
        file_id = int(chunk["file_id"])
        file_record = files_by_id.get(file_id)
        if file_record is None:
            continue

        document_title = file_record["title"]
        needs_extracted_title = should_replace_with_extracted_title(document_title, file_record["filename"] or "")
        page_number: int | None = 1
        if file_record["mime_type"] == "application/pdf":
            if file_id not in file_bytes_by_file_id:
                try:
                    file_bytes_by_file_id[file_id] = await _read_file_bytes(file_record["s3_key"])
                except Exception:
                    file_bytes_by_file_id[file_id] = b""
            if file_id not in page_spans_by_file_id:
                try:
                    data = file_bytes_by_file_id[file_id]
                    page_spans_by_file_id[file_id] = _build_pdf_page_spans(data) if data else []
                except Exception:
                    page_spans_by_file_id[file_id] = []
            page_number = _resolve_page_number(
                int(chunk.get("start_byte") or 0),
                int(chunk.get("end_byte") or 0),
                page_spans_by_file_id[file_id],
            ) or 1
        elif needs_extracted_title and file_id not in file_bytes_by_file_id:
            try:
                file_bytes_by_file_id[file_id] = await _read_file_bytes(file_record["s3_key"])
            except Exception:
                file_bytes_by_file_id[file_id] = b""

        if needs_extracted_title:
            extracted_title = extract_document_title(
                file_record["mime_type"],
                file_bytes_by_file_id.get(file_id, b""),
                file_record["filename"] or "",
            )
            if extracted_title:
                document_title = extracted_title

        citations.append(
            {
                "id": f"c{index}",
                "file_id": file_id,
                "document_title": document_title,
                "page_number": page_number,
                "mime_type": file_record["mime_type"],
            }
        )

    return citations
