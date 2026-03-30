from __future__ import annotations

import logging
import os

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..auth import get_optional_user
from ..config import _env_bool
from ..db import SessionLocal
from ..errors import raise_api_error
from ..models import File, Folder


router = APIRouter(prefix="/viewer", tags=["viewer"])
logger = logging.getLogger(__name__)


S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_USE_SSL = _env_bool("S3_USE_SSL", False)


def _ensure_storage_configured() -> None:
    if not S3_BUCKET:
        raise_api_error(503, "File storage is not configured right now.", "STORAGE_NOT_CONFIGURED")


def _handle_storage_error(exc: ClientError) -> None:
    error_code = str(exc.response.get("Error", {}).get("Code", ""))
    if error_code in {"NoSuchKey", "404", "NotFound"}:
        raise_api_error(404, "The requested file could not be found in storage.", "FILE_NOT_FOUND")
    if error_code == "InvalidRange":
        raise_api_error(416, "The requested byte range is not available for this file.", "INVALID_RANGE")
    if error_code in {"NoSuchBucket", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
        raise_api_error(503, "File storage is temporarily unavailable.", "STORAGE_UNAVAILABLE")
    raise_api_error(502, "File storage returned an error while loading the file.", "FILE_READ_FAILED")


@router.get("/{file_id}")
async def range_proxy(file_id: int, request: Request, user=Depends(get_optional_user)):
    async with SessionLocal() as db:
        try:
            row = await db.execute(
                select(File, Folder.user_id)
                .join(Folder, Folder.id == File.folder_id)
                .where(File.id == file_id)
            )
        except SQLAlchemyError:
            raise_api_error(503, "The file could not be loaded right now. Please try again.", "FILE_LOOKUP_FAILED")

        record = row.first()
        if not record:
            raise_api_error(404, "File not found.", "FILE_NOT_FOUND")

        file_model, owner_id = record
        is_publicly_accessible = file_model.is_public and not file_model.is_copyright_restricted
        if not is_publicly_accessible and owner_id != (user.id if user else None):
            if user is None:
                raise_api_error(401, "Create an account or sign in to view this private file.", "AUTH_REQUIRED")
            raise_api_error(403, "You do not have permission to view this file.", "FILE_VIEW_FORBIDDEN")

    _ensure_storage_configured()
    range_header = request.headers.get("range") or request.headers.get("Range")
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
            params = {"Bucket": S3_BUCKET, "Key": file_model.s3_key}
            if range_header:
                params["Range"] = range_header
            obj = await s3.get_object(**params)
            body = await obj["Body"].read()
    except ClientError as exc:
        _handle_storage_error(exc)
    except BotoCoreError:
        raise_api_error(503, "File storage is temporarily unavailable.", "STORAGE_UNAVAILABLE")
    except Exception:
        logger.exception("Unexpected error while streaming file", extra={"file_id": file_id})
        raise

    status_code = 206 if range_header else 200
    headers = {
        "Content-Type": file_model.mime_type,
        "Accept-Ranges": "bytes",
    }
    content_length = obj.get("ContentLength")
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    if range_header:
        content_range = obj.get("ContentRange") or obj.get("Content-Range")
        if content_range:
            headers["Content-Range"] = content_range

    return Response(content=body, status_code=status_code, headers=headers)
