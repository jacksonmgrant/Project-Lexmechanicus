from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import aioboto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field, validator
from sqlalchemy import Text, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..auth import get_current_user, get_optional_user
from ..config import _env_bool, settings
from ..db import SessionLocal
from ..errors import raise_api_error
from ..models import Bundle, BundleFile, SavedBundle, UserRulesetBundle
from ..models import File as FileModel
from ..models import FileChunk, FileTag, Folder, GameSystem, Ruleset, RulesetAlias, SavedFile, Tag, User
from ..services.bundles import (
    build_bundle_access_condition,
    get_active_bundle_for_ruleset,
    get_default_bundle_ids,
    get_saved_bundle_ids,
    load_accessible_bundle,
    serialize_bundle,
)
from ..services.chunker import iter_chunks
from ..services.embeddings import embed_texts
from ..services.openai_vector_store import OpenAIVectorStoreSyncError, sync_file_to_vector_store
from ..services.parsers import extract_document_title, normalize_text, should_replace_with_extracted_title
from ..services.rulesets import (
    DEFAULT_RULESET_NAME,
    DEFAULT_RULESET_SLUG,
    build_file_access_condition,
    create_ruleset,
    get_active_ruleset,
    get_ruleset_scope_ids,
    get_rulesets_by_ids,
    search_rulesets,
    serialize_ruleset,
)
from ..services.tags import GENERAL_TAG_KIND, ensure_default_game_system_tag, get_or_create_tag, get_tags_by_ids, search_tags, serialize_tag


router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_USE_SSL = _env_bool("S3_USE_SSL", False)
DEFAULT_FOLDER_GAME_SYSTEM_ID = 1
DEFAULT_FOLDER_NAME = "My Uploads"
MAX_UPLOAD_SIZE_BYTES = 75 * 1024 * 1024
DEFAULT_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"},
}


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern=f"^({GENERAL_TAG_KIND})$")

    @validator("name")
    def validate_name(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Enter a tag name.")
        return normalized


class RulesetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list)

    @validator("name")
    def validate_name(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Enter a game system name.")
        return normalized

    @validator("aliases", each_item=True)
    def validate_aliases(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Aliases cannot be blank.")
        return normalized


class FileTagsUpdateRequest(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)


class FileTitleUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @validator("title")
    def validate_title(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Enter a title before saving.")
        return normalized


class FileGameSystemUpdateRequest(BaseModel):
    ruleset_id: int = Field(ge=1)


class ActiveGameSystemUpdateRequest(BaseModel):
    ruleset_id: int = Field(ge=1)


class BundleCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    ruleset_id: int = Field(ge=1)
    file_ids: list[int] = Field(default_factory=list)
    is_public: bool = False

    @validator("title")
    def validate_title(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Enter a bundle title.")
        return normalized

    @validator("description")
    def validate_description(cls, value: str):
        return value.strip()

    @validator("file_ids")
    def validate_file_ids(cls, value: list[int]):
        normalized_ids: list[int] = []
        seen: set[int] = set()
        for item in value:
            if not isinstance(item, int) or item < 1:
                raise ValueError("Choose at least one valid file.")
            if item not in seen:
                normalized_ids.append(item)
                seen.add(item)
        if not normalized_ids:
            raise ValueError("Choose at least one file for the bundle.")
        return normalized_ids


class ActiveBundleUpdateRequest(BaseModel):
    ruleset_id: int = Field(ge=1)
    bundle_id: int | None = Field(default=None, ge=1)


class BundleFilesUpdateRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list)

    @validator("file_ids")
    def validate_file_ids(cls, value: list[int]):
        normalized_ids: list[int] = []
        seen: set[int] = set()
        for item in value:
            if not isinstance(item, int) or item < 1:
                raise ValueError("Choose at least one valid file.")
            if item not in seen:
                normalized_ids.append(item)
                seen.add(item)
        if not normalized_ids:
            raise ValueError("Choose at least one file.")
        return normalized_ids


class BundleTitleUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)

    @validator("title")
    def validate_title(cls, value: str):
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Enter a bundle title.")
        return normalized


def _ensure_storage_configured() -> None:
    if not S3_BUCKET:
        raise_api_error(503, "File storage is not configured right now.", "STORAGE_NOT_CONFIGURED")


def _normalize_filename(upload: UploadFile) -> tuple[str, str, str]:
    normalized_name = Path((upload.filename or "").strip()).name
    if not normalized_name:
        raise_api_error(422, "Select a file before uploading.", "FILE_REQUIRED")

    extension = Path(normalized_name).suffix.lower()
    if extension not in DEFAULT_MIME_BY_EXTENSION:
        raise_api_error(415, "Unsupported file type. Upload a PDF, TXT, or Markdown file.", "UNSUPPORTED_FILE_TYPE")

    mime_type = (upload.content_type or DEFAULT_MIME_BY_EXTENSION[extension]).strip().lower()
    if mime_type not in ALLOWED_CONTENT_TYPES[extension]:
        raise_api_error(415, "Unsupported file type. Upload a PDF, TXT, or Markdown file.", "UNSUPPORTED_FILE_TYPE")

    return normalized_name, extension, DEFAULT_MIME_BY_EXTENSION[extension]


def _validate_upload_payload(*, folder_id: int, filename: str, data: bytes) -> None:
    if folder_id < 1:
        raise_api_error(422, "Choose a valid destination folder.", "INVALID_FOLDER_ID")
    if not filename:
        raise_api_error(422, "Select a file before uploading.", "FILE_REQUIRED")
    if not data:
        raise_api_error(422, "The selected file is empty.", "EMPTY_FILE")
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise_api_error(413, "The selected file is too large. Upload files up to 75 MB.", "FILE_TOO_LARGE")


def _handle_storage_client_error(exc: ClientError, *, action: str, missing_code: str | None = None, missing_message: str | None = None) -> None:
    error_code = str(exc.response.get("Error", {}).get("Code", ""))
    if missing_code and error_code in {"NoSuchKey", "404", "NotFound"}:
        raise_api_error(404, missing_message or "The requested file could not be found.", missing_code)
    if error_code == "InvalidRange":
        raise_api_error(416, "The requested byte range is not available for this file.", "INVALID_RANGE")
    if error_code in {"NoSuchBucket", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
        raise_api_error(503, "File storage is temporarily unavailable.", "STORAGE_UNAVAILABLE")
    raise_api_error(502, f"File storage failed while trying to {action}.", "STORAGE_OPERATION_FAILED")


async def _ensure_storage_bucket_exists(s3) -> None:
    _ensure_storage_configured()
    try:
        await s3.head_bucket(Bucket=S3_BUCKET)
        return
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code not in {"NoSuchBucket", "404", "NotFound"}:
            _handle_storage_client_error(exc, action="check the storage bucket")

    create_bucket_params: dict[str, object] = {"Bucket": S3_BUCKET}
    if S3_REGION and S3_REGION != "us-east-1":
        create_bucket_params["CreateBucketConfiguration"] = {"LocationConstraint": S3_REGION}

    try:
        await s3.create_bucket(**create_bucket_params)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            _handle_storage_client_error(exc, action="create the storage bucket")


async def _put_file_in_storage(key: str, data: bytes, mime_type: str) -> None:
    _ensure_storage_configured()
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
            await _ensure_storage_bucket_exists(s3)
            await s3.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=mime_type,
            )
    except ClientError as exc:
        _handle_storage_client_error(exc, action="store the uploaded file")
    except BotoCoreError:
        raise_api_error(503, "File storage is temporarily unavailable.", "STORAGE_UNAVAILABLE")


async def _delete_file_from_storage(key: str) -> None:
    _ensure_storage_configured()
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
            await s3.delete_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as exc:
        _handle_storage_client_error(
            exc,
            action="delete the file",
            missing_code="FILE_NOT_FOUND",
            missing_message="The file is already gone from storage.",
        )
    except BotoCoreError:
        raise_api_error(503, "File storage is temporarily unavailable.", "STORAGE_UNAVAILABLE")


async def _ensure_default_folder_game_system(db) -> int:
    existing = await db.get(GameSystem, DEFAULT_FOLDER_GAME_SYSTEM_ID)
    if existing:
        return existing.id

    await db.execute(
        insert(GameSystem).values(
            {
                "id": DEFAULT_FOLDER_GAME_SYSTEM_ID,
                "name": DEFAULT_RULESET_NAME,
                "slug": DEFAULT_RULESET_SLUG,
            }
        )
    )
    return DEFAULT_FOLDER_GAME_SYSTEM_ID


async def _resolve_upload_folder_id(db, *, requested_folder_id: int, user_id: int) -> int:
    requested_folder = await db.get(Folder, requested_folder_id)
    if requested_folder is not None:
        if requested_folder.user_id != user_id:
            raise_api_error(403, "You do not have permission to upload to that folder.", "FOLDER_FORBIDDEN")
        return requested_folder.id

    existing_folder_id = await db.scalar(select(Folder.id).where(Folder.user_id == user_id).order_by(Folder.id).limit(1))
    if existing_folder_id is not None:
        return existing_folder_id

    game_system_id = await _ensure_default_folder_game_system(db)
    created_folder = await db.execute(
        insert(Folder)
        .values(
            {
                "user_id": user_id,
                "game_system_id": game_system_id,
                "name": DEFAULT_FOLDER_NAME,
            }
        )
        .returning(Folder.id)
    )
    return created_folder.scalar_one()


def _parse_tag_ids(raw_value: str) -> list[int]:
    if not raw_value.strip():
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        raise_api_error(422, "The selected tags were invalid.", "INVALID_TAG_IDS")

    if not isinstance(payload, list):
        raise_api_error(422, "The selected tags were invalid.", "INVALID_TAG_IDS")

    normalized_ids: list[int] = []
    seen: set[int] = set()
    for item in payload:
        if not isinstance(item, int) or item < 1:
            raise_api_error(422, "The selected tags were invalid.", "INVALID_TAG_IDS")
        if item not in seen:
            normalized_ids.append(item)
            seen.add(item)
    return normalized_ids


async def _resolve_general_tags(db, *, tag_ids: list[int]) -> list[Tag]:
    tags = await get_tags_by_ids(db, ids=tag_ids, kind=GENERAL_TAG_KIND)
    if len(tags) != len(tag_ids):
        raise_api_error(422, "One or more selected tags no longer exist.", "TAGS_NOT_FOUND")
    return tags


async def _resolve_ruleset(db, *, requested_ruleset_id: int | None, user_id: int | None) -> Ruleset:
    if requested_ruleset_id is not None:
        ruleset = await db.get(Ruleset, requested_ruleset_id)
        if ruleset is None:
            raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")
        return ruleset

    active_ruleset, _ = await get_active_ruleset(db, user_id=user_id)
    if active_ruleset is None:
        raise_api_error(422, "Choose a game system before continuing.", "RULESET_REQUIRED")
    return active_ruleset


async def _serialize_file_metadata(db, file_ids: list[int]) -> tuple[dict[int, dict[str, object] | None], dict[int, list[dict[str, object]]]]:
    if not file_ids:
        return {}, {}

    ruleset_rows = (
        await db.execute(
            select(FileModel.id, Ruleset)
            .join(Ruleset, Ruleset.id == FileModel.ruleset_id)
            .where(FileModel.id.in_(file_ids))
        )
    ).all()
    rulesets = {file_id: serialize_ruleset(ruleset) for file_id, ruleset in ruleset_rows}

    tag_rows = (
        await db.execute(
            select(FileTag.file_id, Tag)
            .join(Tag, Tag.id == FileTag.tag_id)
            .where(FileTag.file_id.in_(file_ids))
            .order_by(FileTag.file_id, func.lower(Tag.name), Tag.id)
        )
    ).all()
    tags_by_file: dict[int, list[dict[str, object]]] = {file_id: [] for file_id in file_ids}
    for file_id, tag in tag_rows:
        tags_by_file.setdefault(file_id, []).append(serialize_tag(tag))

    return rulesets, tags_by_file


async def _load_saved_file_ids(db, *, user_id: int | None, file_ids: list[int]) -> set[int]:
    if user_id is None or not file_ids:
        return set()
    rows = await db.execute(
        select(SavedFile.file_id)
        .where(
            SavedFile.user_id == user_id,
            SavedFile.file_id.in_(file_ids),
        )
    )
    return set(rows.scalars().all())


async def _load_owned_file(db, *, file_id: int, user_id: int) -> FileModel:
    file_model = await db.scalar(
        select(FileModel)
        .join(Folder, Folder.id == FileModel.folder_id)
        .where(FileModel.id == file_id, Folder.user_id == user_id)
    )
    if file_model is None:
        raise_api_error(404, "File not found.", "FILE_NOT_FOUND")
    return file_model


async def _load_accessible_file(db, *, file_id: int, user_id: int) -> FileModel:
    file_model = await db.scalar(
        select(FileModel)
        .join(Folder, Folder.id == FileModel.folder_id)
        .where(
            FileModel.id == file_id,
            build_file_access_condition(user_id=user_id),
        )
    )
    if file_model is None:
        raise_api_error(404, "File not found.", "FILE_NOT_FOUND")
    return file_model


async def _load_owned_bundle(db, *, bundle_id: int, user_id: int) -> Bundle:
    bundle = await db.get(Bundle, bundle_id)
    if bundle is None:
        raise_api_error(404, "Bundle not found.", "BUNDLE_NOT_FOUND")
    if bundle.owner_id != user_id:
        raise_api_error(403, "You do not have permission to edit this bundle.", "BUNDLE_EDIT_FORBIDDEN")
    return bundle


async def _delete_empty_bundles(db, *, bundle_ids: list[int]) -> set[int]:
    normalized_bundle_ids = sorted({bundle_id for bundle_id in bundle_ids if bundle_id})
    if not normalized_bundle_ids:
        return set()

    empty_bundle_ids = set(
        (
            await db.execute(
                select(Bundle.id).where(
                    Bundle.id.in_(normalized_bundle_ids),
                    ~select(BundleFile.bundle_id).where(BundleFile.bundle_id == Bundle.id).exists(),
                )
            )
        ).scalars().all()
    )
    if not empty_bundle_ids:
        return set()

    await db.execute(delete(Bundle).where(Bundle.id.in_(empty_bundle_ids)))
    return empty_bundle_ids


async def _delete_empty_bundles_for_file(db, *, file_id: int) -> None:
    affected_bundle_ids = list(
        (
            await db.execute(
                select(BundleFile.bundle_id).where(BundleFile.file_id == file_id)
            )
        ).scalars().all()
    )
    if not affected_bundle_ids:
        return

    await _delete_empty_bundles(db, bundle_ids=affected_bundle_ids)


async def _serialize_bundle_detail_payload(db, *, bundle: Bundle, user_id: int) -> dict[str, object]:
    bundle_owner = await db.get(User, bundle.owner_id)
    bundle_ruleset = await db.get(Ruleset, bundle.ruleset_id)
    file_count = int(await db.scalar(select(func.count(BundleFile.file_id)).where(BundleFile.bundle_id == bundle.id)) or 0)
    saved_bundle_ids = await get_saved_bundle_ids(db, user_id=user_id, bundle_ids=[bundle.id])
    default_bundle_ids = await get_default_bundle_ids(db, user_id=user_id, bundle_ids=[bundle.id])
    preview_titles = await _load_bundle_preview_titles(db, bundle_ids=[bundle.id])

    chunk_counts = select(FileChunk.file_id, func.count().label("chunk_count")).group_by(FileChunk.file_id).subquery()
    save_counts = select(SavedFile.file_id, func.count().label("save_count")).group_by(SavedFile.file_id).subquery()
    file_rows = (
        await db.execute(
            select(
                FileModel.id,
                FileModel.title,
                FileModel.description,
                FileModel.filename,
                FileModel.mime_type,
                FileModel.size_bytes,
                FileModel.is_public,
                FileModel.openai_vector_store_status,
                FileModel.ruleset_id,
                Folder.id.label("folder_id"),
                User.display_name.label("uploader_display_name"),
                chunk_counts.c.chunk_count,
                save_counts.c.save_count,
            )
            .join(BundleFile, BundleFile.file_id == FileModel.id)
            .join(Folder, Folder.id == FileModel.folder_id)
            .join(User, User.id == Folder.user_id)
            .outerjoin(chunk_counts, chunk_counts.c.file_id == FileModel.id)
            .outerjoin(save_counts, save_counts.c.file_id == FileModel.id)
            .where(BundleFile.bundle_id == bundle.id)
            .order_by(BundleFile.sort_order, FileModel.title, FileModel.id)
        )
    ).mappings().all()

    file_ids = [row["id"] for row in file_rows]
    rulesets, tags_by_file = await _serialize_file_metadata(db, file_ids)
    saved_file_ids = await _load_saved_file_ids(db, user_id=user_id, file_ids=file_ids)

    return {
        "bundle": serialize_bundle(
            bundle,
            ruleset=bundle_ruleset,
            owner=bundle_owner,
            file_count=file_count,
            is_saved=bundle.id in saved_bundle_ids,
            is_default=bundle.id in default_bundle_ids,
            preview_titles=preview_titles.get(bundle.id, []),
        ),
        "files": [
            _serialize_file_listing_row(
                row,
                rulesets=rulesets,
                tags_by_file=tags_by_file,
                saved_file_ids=saved_file_ids,
            )
            for row in file_rows
        ],
    }


async def _serialize_active_bundle_payload(db, *, user_id: int | None, ruleset_id: int | None) -> dict[str, object] | None:
    active_bundle = await get_active_bundle_for_ruleset(db, user_id=user_id, ruleset_id=ruleset_id)
    if active_bundle is None:
        return None

    bundle_owner = await db.get(User, active_bundle.owner_id)
    bundle_ruleset = await db.get(Ruleset, active_bundle.ruleset_id)
    file_count = int(
        await db.scalar(
            select(func.count(BundleFile.file_id)).where(BundleFile.bundle_id == active_bundle.id)
        )
        or 0
    )
    is_saved = active_bundle.owner_id == user_id or active_bundle.id in await get_saved_bundle_ids(db, user_id=user_id, bundle_ids=[active_bundle.id])
    return serialize_bundle(
        active_bundle,
        ruleset=bundle_ruleset,
        owner=bundle_owner,
        file_count=file_count,
        is_saved=is_saved,
        is_default=True,
    )


async def _load_bundle_preview_titles(db, *, bundle_ids: list[int], limit_per_bundle: int = 4) -> dict[int, list[str]]:
    if not bundle_ids:
        return {}

    rows = (
        await db.execute(
            select(BundleFile.bundle_id, FileModel.title)
            .join(FileModel, FileModel.id == BundleFile.file_id)
            .where(BundleFile.bundle_id.in_(bundle_ids))
            .order_by(BundleFile.bundle_id, BundleFile.sort_order, FileModel.title, FileModel.id)
        )
    ).all()
    preview_by_bundle: dict[int, list[str]] = {}
    for bundle_id, title in rows:
        titles = preview_by_bundle.setdefault(bundle_id, [])
        if len(titles) < limit_per_bundle:
            titles.append(title)
    return preview_by_bundle


def _serialize_file_listing_row(
    row,
    *,
    rulesets: dict[int, dict[str, object] | None],
    tags_by_file: dict[int, list[dict[str, object]]],
    saved_file_ids: set[int],
) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "filename": row["filename"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "is_public": row["is_public"],
        "is_saved": row["id"] in saved_file_ids,
        "status": row["openai_vector_store_status"] or "ready",
        "folder_id": row["folder_id"],
        "game_system": rulesets.get(row["id"]),
        "game_system_id": row["ruleset_id"],
        "tags": tags_by_file.get(row["id"], []),
        "uploader_name": row["uploader_display_name"] or "Anonymous",
        "chunk_count": row["chunk_count"] or 0,
        "save_count": row["save_count"] or 0,
    }


@router.get("/tags")
async def list_tags(
    q: str = Query("", max_length=120),
    kind: str | None = Query(None, pattern=f"^({GENERAL_TAG_KIND})$"),
    limit: int = Query(12, ge=1, le=50),
):
    async with SessionLocal() as db:
        try:
            tags = await search_tags(db, query=q, kind=kind or GENERAL_TAG_KIND, limit=limit)
        except SQLAlchemyError:
            logger.exception("Tag search failed", extra={"q": q.strip()})
            raise_api_error(503, "Tags are temporarily unavailable. Please try again.", "TAG_SEARCH_FAILED")
    return [serialize_tag(tag) for tag in tags]


@router.post("/tags")
async def create_tag(body: TagCreateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            tag = await get_or_create_tag(db, name=body.name, kind=GENERAL_TAG_KIND)
            await db.commit()
        except ValueError as exc:
            await db.rollback()
            raise_api_error(409, str(exc), "TAG_KIND_CONFLICT")
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Tag creation failed", extra={"user_id": user.id, "name": body.name})
            raise_api_error(503, "The tag could not be created right now. Please try again.", "TAG_CREATE_FAILED")
    return serialize_tag(tag)


@router.get("/game-systems")
async def list_game_systems(user=Depends(get_optional_user)):
    async with SessionLocal() as db:
        try:
            active_ruleset, available_rulesets = await get_active_ruleset(db, user_id=user.id if user else None)
            active_bundle = await _serialize_active_bundle_payload(
                db,
                user_id=user.id if user else None,
                ruleset_id=active_ruleset.id if active_ruleset else None,
            )
            if user is not None:
                await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Ruleset lookup failed", extra={"user_id": user.id if user else None})
            raise_api_error(503, "Game systems are temporarily unavailable. Please try again.", "RULESET_LOOKUP_FAILED")
    return {
        "active_game_system": serialize_ruleset(active_ruleset),
        "available_game_systems": [serialize_ruleset(ruleset) for ruleset in available_rulesets],
        "active_bundle": active_bundle,
    }


@router.get("/game-systems/search")
async def search_game_systems(q: str = Query("", max_length=160), limit: int = Query(10, ge=1, le=30)):
    async with SessionLocal() as db:
        try:
            rulesets = await search_rulesets(db, query=q, limit=limit)
        except SQLAlchemyError:
            logger.exception("Ruleset search failed", extra={"q": q.strip()})
            raise_api_error(503, "Game systems are temporarily unavailable. Please try again.", "RULESET_SEARCH_FAILED")
    return [serialize_ruleset(ruleset) for ruleset in rulesets]


@router.post("/game-systems")
async def create_game_system(body: RulesetCreateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            ruleset = await create_ruleset(
                db,
                name=body.name,
                aliases=body.aliases,
            )
            db_user = await db.get(User, user.id)
            if db_user is not None:
                db_user.active_ruleset_id = ruleset.id
            await db.commit()
        except ValueError as exc:
            await db.rollback()
            raise_api_error(409, str(exc), "RULESET_CREATE_CONFLICT")
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Ruleset creation failed", extra={"user_id": user.id})
            raise_api_error(503, "The game system could not be created right now. Please try again.", "RULESET_CREATE_FAILED")
    return serialize_ruleset(ruleset)


@router.put("/game-systems/active")
async def update_active_game_system(body: ActiveGameSystemUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            ruleset = await db.get(Ruleset, body.ruleset_id)
            if ruleset is None:
                raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")
            db_user = await db.get(User, user.id)
            if db_user is None:
                raise_api_error(404, "User account not found.", "USER_NOT_FOUND")
            db_user.active_ruleset_id = ruleset.id
            await db.commit()

            active_ruleset, refreshed_rulesets = await get_active_ruleset(db, user_id=user.id)
            active_bundle = await _serialize_active_bundle_payload(
                db,
                user_id=user.id,
                ruleset_id=active_ruleset.id if active_ruleset else None,
            )
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Active ruleset update failed", extra={"user_id": user.id, "ruleset_id": body.ruleset_id})
            raise_api_error(503, "The active game system could not be updated right now.", "RULESET_UPDATE_FAILED")
    return {
        "active_game_system": serialize_ruleset(active_ruleset),
        "available_game_systems": [serialize_ruleset(ruleset) for ruleset in refreshed_rulesets],
        "active_bundle": active_bundle,
    }


@router.get("/bundles")
async def list_bundles(
    scope: str = Query("browse", pattern="^(browse|mine|saved)$"),
    q: str = Query("", max_length=200),
    ruleset_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_optional_user),
):
    if scope in {"mine", "saved"} and user is None:
        raise_api_error(401, "Create an account or sign in to use this feature.", "AUTH_REQUIRED")

    async with SessionLocal() as db:
        try:
            _, scoped_ruleset_ids = await get_ruleset_scope_ids(db, ruleset_id=ruleset_id)
            if ruleset_id is not None and scoped_ruleset_ids == []:
                raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")

            bundle_counts = select(BundleFile.bundle_id, func.count().label("file_count")).group_by(BundleFile.bundle_id).subquery()
            bundle_save_counts = select(SavedBundle.bundle_id, func.count().label("save_count")).group_by(SavedBundle.bundle_id).subquery()
            stmt = (
                select(Bundle, Ruleset, User, bundle_counts.c.file_count, bundle_save_counts.c.save_count)
                .join(Ruleset, Ruleset.id == Bundle.ruleset_id)
                .join(User, User.id == Bundle.owner_id)
                .outerjoin(bundle_counts, bundle_counts.c.bundle_id == Bundle.id)
                .outerjoin(bundle_save_counts, bundle_save_counts.c.bundle_id == Bundle.id)
                .order_by(Bundle.id.desc())
                .limit(limit)
            )

            if scope == "mine":
                stmt = stmt.where(Bundle.owner_id == user.id)
            elif scope == "saved":
                stmt = (
                    stmt.join(SavedBundle, SavedBundle.bundle_id == Bundle.id)
                    .where(
                        SavedBundle.user_id == user.id,
                        build_bundle_access_condition(user_id=user.id),
                    )
                )
            else:
                stmt = stmt.where(build_bundle_access_condition(user_id=user.id if user else None))

            if scoped_ruleset_ids is not None:
                stmt = stmt.where(Bundle.ruleset_id.in_(scoped_ruleset_ids))

            normalized_q = q.strip().lower()
            if normalized_q:
                file_title_match = (
                    select(BundleFile.bundle_id)
                    .join(FileModel, FileModel.id == BundleFile.file_id)
                    .where(
                        BundleFile.bundle_id == Bundle.id,
                        or_(
                            func.lower(FileModel.title).like(f"%{normalized_q}%"),
                            func.lower(FileModel.filename).like(f"%{normalized_q}%"),
                        ),
                    )
                    .exists()
                )
                stmt = stmt.where(
                    or_(
                        func.lower(Bundle.title).like(f"%{normalized_q}%"),
                        func.lower(func.coalesce(Bundle.description, "")).like(f"%{normalized_q}%"),
                        func.cast(Bundle.id, Text) == normalized_q,
                        file_title_match,
                    )
                )

            rows = (await db.execute(stmt)).all()
            bundles = [row[0] for row in rows]
            bundle_ids = [bundle.id for bundle in bundles]
            preview_by_bundle = await _load_bundle_preview_titles(db, bundle_ids=bundle_ids)
            saved_bundle_ids = set(bundle_ids) if scope == "saved" and user is not None else await get_saved_bundle_ids(
                db,
                user_id=user.id if user else None,
                bundle_ids=bundle_ids,
            )
            default_bundle_ids = await get_default_bundle_ids(
                db,
                user_id=user.id if user else None,
                bundle_ids=bundle_ids,
            )
        except SQLAlchemyError:
            logger.exception("Bundle listing failed", extra={"scope": scope, "user_id": user.id if user else None, "ruleset_id": ruleset_id})
            raise_api_error(503, "The bundle list is temporarily unavailable. Please try again.", "BUNDLE_LIST_UNAVAILABLE")

    return [
        serialize_bundle(
            bundle,
            ruleset=ruleset,
            owner=owner,
            file_count=int(file_count or 0),
            save_count=int(save_count or 0),
            is_saved=bundle.id in saved_bundle_ids,
            is_default=bundle.id in default_bundle_ids,
            preview_titles=preview_by_bundle.get(bundle.id, []),
        )
        for bundle, ruleset, owner, file_count, save_count in rows
    ]


@router.post("/bundles")
async def create_bundle(body: BundleCreateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            selected_ruleset = await _resolve_ruleset(db, requested_ruleset_id=body.ruleset_id, user_id=user.id)
            file_rows = (
                await db.execute(
                    select(FileModel.id, FileModel.ruleset_id, FileModel.is_public)
                    .join(Folder, Folder.id == FileModel.folder_id)
                    .where(
                        FileModel.id.in_(body.file_ids),
                        build_file_access_condition(user_id=user.id),
                    )
                )
            ).all()
            files_by_id = {file_id: {"ruleset_id": file_ruleset_id, "is_public": is_public} for file_id, file_ruleset_id, is_public in file_rows}

            missing_ids = [file_id for file_id in body.file_ids if file_id not in files_by_id]
            if missing_ids:
                raise_api_error(422, "One or more selected files are no longer available.", "BUNDLE_FILES_NOT_FOUND")

            invalid_ruleset_ids = [file_id for file_id in body.file_ids if files_by_id[file_id]["ruleset_id"] != selected_ruleset.id]
            if invalid_ruleset_ids:
                raise_api_error(422, "Every file in a bundle must belong to the selected game system.", "BUNDLE_RULESET_MISMATCH")

            if body.is_public and any(not files_by_id[file_id]["is_public"] for file_id in body.file_ids):
                raise_api_error(422, "Public bundles can only include public files.", "BUNDLE_PUBLIC_FILES_REQUIRED")

            created_bundle_id = (
                await db.execute(
                    insert(Bundle)
                    .values(
                        {
                            "owner_id": user.id,
                            "ruleset_id": selected_ruleset.id,
                            "title": body.title,
                            "description": body.description or None,
                            "is_public": body.is_public,
                        }
                    )
                    .returning(Bundle.id)
                )
            ).scalar_one()

            await db.execute(
                insert(BundleFile),
                [
                    {
                        "bundle_id": created_bundle_id,
                        "file_id": file_id,
                        "sort_order": index,
                    }
                    for index, file_id in enumerate(body.file_ids)
                ],
            )
            await db.commit()

            created_bundle = await db.get(Bundle, created_bundle_id)
            bundle_owner = await db.get(User, user.id)
        except IntegrityError:
            await db.rollback()
            raise_api_error(409, "You already have a bundle with that title for this game system.", "BUNDLE_TITLE_CONFLICT")
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Bundle creation failed", extra={"user_id": user.id, "ruleset_id": body.ruleset_id})
            raise_api_error(503, "The bundle could not be created right now. Please try again.", "BUNDLE_CREATE_FAILED")

    return serialize_bundle(
        created_bundle,
        ruleset=selected_ruleset,
        owner=bundle_owner,
        file_count=len(body.file_ids),
        is_saved=False,
        is_default=False,
    )


@router.get("/bundles/{bundle_id}")
async def get_bundle_detail(bundle_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await _load_owned_bundle(db, bundle_id=bundle_id, user_id=user.id)
            payload = await _serialize_bundle_detail_payload(db, bundle=bundle, user_id=user.id)
        except SQLAlchemyError:
            logger.exception("Bundle detail load failed", extra={"bundle_id": bundle_id, "user_id": user.id})
            raise_api_error(503, "The bundle could not be loaded right now.", "BUNDLE_DETAIL_FAILED")
    return payload


@router.post("/bundles/{bundle_id}/files")
async def add_files_to_bundle(bundle_id: int, body: BundleFilesUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await _load_owned_bundle(db, bundle_id=bundle_id, user_id=user.id)
            file_rows = (
                await db.execute(
                    select(FileModel.id, FileModel.ruleset_id, FileModel.is_public)
                    .join(Folder, Folder.id == FileModel.folder_id)
                    .where(
                        FileModel.id.in_(body.file_ids),
                        build_file_access_condition(user_id=user.id),
                    )
                )
            ).all()
            files_by_id = {file_id: {"ruleset_id": ruleset_id, "is_public": is_public} for file_id, ruleset_id, is_public in file_rows}

            missing_ids = [file_id for file_id in body.file_ids if file_id not in files_by_id]
            if missing_ids:
                raise_api_error(422, "One or more selected files are no longer available.", "BUNDLE_FILES_NOT_FOUND")

            invalid_ruleset_ids = [file_id for file_id in body.file_ids if files_by_id[file_id]["ruleset_id"] != bundle.ruleset_id]
            if invalid_ruleset_ids:
                raise_api_error(422, "Every file in a bundle must belong to the bundle's game system.", "BUNDLE_RULESET_MISMATCH")

            if bundle.is_public and any(not files_by_id[file_id]["is_public"] for file_id in body.file_ids):
                raise_api_error(422, "Public bundles can only include public files.", "BUNDLE_PUBLIC_FILES_REQUIRED")

            existing_file_ids = set(
                (
                    await db.execute(
                        select(BundleFile.file_id).where(BundleFile.bundle_id == bundle.id)
                    )
                ).scalars().all()
            )
            new_file_ids = [file_id for file_id in body.file_ids if file_id not in existing_file_ids]

            if new_file_ids:
                next_sort_order = int(
                    await db.scalar(
                        select(func.max(BundleFile.sort_order)).where(BundleFile.bundle_id == bundle.id)
                    )
                    or -1
                ) + 1
                await db.execute(
                    insert(BundleFile),
                    [
                        {
                            "bundle_id": bundle.id,
                            "file_id": file_id,
                            "sort_order": next_sort_order + index,
                        }
                        for index, file_id in enumerate(new_file_ids)
                    ],
                )
            await db.commit()
            payload = await _serialize_bundle_detail_payload(db, bundle=bundle, user_id=user.id)
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Bundle file add failed", extra={"bundle_id": bundle_id, "user_id": user.id})
            raise_api_error(503, "The bundle could not be updated right now.", "BUNDLE_FILE_ADD_FAILED")
    return payload


@router.post("/bundles/{bundle_id}/saved")
async def save_bundle(bundle_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await load_accessible_bundle(db, bundle_id=bundle_id, user_id=user.id)
            if bundle is None:
                raise_api_error(404, "Bundle not found.", "BUNDLE_NOT_FOUND")
            existing = await db.scalar(
                select(SavedBundle.id).where(
                    SavedBundle.user_id == user.id,
                    SavedBundle.bundle_id == bundle_id,
                )
            )
            if existing is None:
                db.add(SavedBundle(user_id=user.id, bundle_id=bundle_id))
                await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The bundle could not be saved right now.", "BUNDLE_SAVE_FAILED")
    return {"saved": True}


@router.delete("/bundles/{bundle_id}/saved")
async def unsave_bundle(bundle_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            await db.execute(
                delete(SavedBundle).where(
                    SavedBundle.user_id == user.id,
                    SavedBundle.bundle_id == bundle_id,
                )
            )
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The bundle could not be unsaved right now.", "BUNDLE_UNSAVE_FAILED")
    return {"saved": False}


@router.delete("/bundles/{bundle_id}/files/{file_id}")
async def remove_file_from_bundle(bundle_id: int, file_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await _load_owned_bundle(db, bundle_id=bundle_id, user_id=user.id)
            result = await db.execute(
                delete(BundleFile).where(
                    BundleFile.bundle_id == bundle.id,
                    BundleFile.file_id == file_id,
                )
            )
            if not result.rowcount:
                raise_api_error(404, "That file is not in the bundle.", "BUNDLE_FILE_NOT_FOUND")

            deleted_bundle_ids = await _delete_empty_bundles(db, bundle_ids=[bundle.id])
            await db.commit()

            if bundle.id in deleted_bundle_ids:
                return {"deleted": True}

            payload = await _serialize_bundle_detail_payload(db, bundle=bundle, user_id=user.id)
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Bundle file removal failed", extra={"bundle_id": bundle_id, "file_id": file_id, "user_id": user.id})
            raise_api_error(503, "The bundle could not be updated right now.", "BUNDLE_FILE_REMOVE_FAILED")
    return {"deleted": False, **payload}


@router.put("/bundles/{bundle_id}/title")
async def update_bundle_title(bundle_id: int, body: BundleTitleUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await db.get(Bundle, bundle_id)
            if bundle is None:
                raise_api_error(404, "Bundle not found.", "BUNDLE_NOT_FOUND")
            if bundle.owner_id != user.id:
                raise_api_error(403, "You do not have permission to edit this bundle.", "BUNDLE_EDIT_FORBIDDEN")
            bundle.title = body.title
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise_api_error(409, "You already have a bundle with that title for this game system.", "BUNDLE_TITLE_CONFLICT")
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The bundle title could not be updated right now.", "BUNDLE_TITLE_UPDATE_FAILED")
    return {"title": body.title}


@router.put("/bundles/active")
async def update_active_bundle(body: ActiveBundleUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            ruleset = await db.get(Ruleset, body.ruleset_id)
            if ruleset is None:
                raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")

            if body.bundle_id is None:
                await db.execute(
                    delete(UserRulesetBundle).where(
                        UserRulesetBundle.user_id == user.id,
                        UserRulesetBundle.ruleset_id == ruleset.id,
                    )
                )
                await db.commit()
                return {"active_bundle": None}

            bundle = await load_accessible_bundle(db, bundle_id=body.bundle_id, user_id=user.id, ruleset_id=ruleset.id)
            if bundle is None:
                raise_api_error(422, "Choose a valid bundle for that game system.", "BUNDLE_NOT_FOUND")

            existing = await db.scalar(
                select(UserRulesetBundle).where(
                    UserRulesetBundle.user_id == user.id,
                    UserRulesetBundle.ruleset_id == ruleset.id,
                )
            )
            if existing is None:
                db.add(UserRulesetBundle(user_id=user.id, ruleset_id=ruleset.id, bundle_id=bundle.id))
            else:
                existing.bundle_id = bundle.id
            await db.commit()

            bundle_owner = await db.get(User, bundle.owner_id)
            saved_bundle_ids = await get_saved_bundle_ids(db, user_id=user.id, bundle_ids=[bundle.id])
            file_count = int(await db.scalar(select(func.count(BundleFile.file_id)).where(BundleFile.bundle_id == bundle.id)) or 0)
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("Active bundle update failed", extra={"user_id": user.id, "ruleset_id": body.ruleset_id, "bundle_id": body.bundle_id})
            raise_api_error(503, "The active bundle could not be updated right now.", "BUNDLE_ACTIVE_UPDATE_FAILED")

    return {
        "active_bundle": serialize_bundle(
            bundle,
            ruleset=ruleset,
            owner=bundle_owner,
            file_count=file_count,
            is_saved=bundle.id in saved_bundle_ids,
            is_default=True,
        )
    }


@router.delete("/bundles/{bundle_id}")
async def delete_bundle(bundle_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            bundle = await db.get(Bundle, bundle_id)
            if bundle is None:
                raise_api_error(404, "Bundle not found.", "BUNDLE_NOT_FOUND")
            if bundle.owner_id != user.id:
                raise_api_error(403, "You do not have permission to delete this bundle.", "BUNDLE_DELETE_FORBIDDEN")
            await db.execute(delete(Bundle).where(Bundle.id == bundle_id))
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The bundle could not be deleted right now.", "BUNDLE_DELETE_FAILED")
    return {"status": "ok"}


@router.post("/")
async def upload_file(
    folder_id: int = Form(...),
    is_public: bool = Form(False),
    title: str = Form(...),
    description: str = Form(""),
    tag_ids: str = Form("[]"),
    ruleset_id: int | None = Form(None),
    f: UploadFile = File(...),
    user=Depends(get_current_user),
):
    normalized_filename, _, normalized_mime_type = _normalize_filename(f)
    normalized_title = title.strip()
    normalized_description = description.strip()
    parsed_tag_ids = _parse_tag_ids(tag_ids)
    if not normalized_title:
        raise_api_error(422, "Enter a title before uploading.", "TITLE_REQUIRED")
    if len(normalized_title) > 120:
        raise_api_error(422, "Keep the title under 120 characters.", "TITLE_TOO_LONG")
    if len(normalized_description) > 1000:
        raise_api_error(422, "Keep the description under 1000 characters.", "DESCRIPTION_TOO_LONG")
    try:
        data = await f.read()
    except OSError:
        raise_api_error(400, "The uploaded file could not be read.", "FILE_READ_FAILED")

    _validate_upload_payload(folder_id=folder_id, filename=normalized_filename, data=data)

    if should_replace_with_extracted_title(normalized_title, normalized_filename):
        extracted_title = extract_document_title(normalized_mime_type, data, normalized_filename)
        if extracted_title:
            normalized_title = extracted_title

    try:
        text_content = normalize_text(normalized_mime_type, data)
    except Exception:
        logger.exception("Upload parsing failed", extra={"user_id": user.id, "filename": normalized_filename})
        raise_api_error(422, "The uploaded file could not be parsed. Try a different PDF, TXT, or Markdown file.", "FILE_PARSE_FAILED")

    chunks = list(iter_chunks(text_content))
    if not chunks:
        raise_api_error(422, "No readable text was found in that file.", "NO_READABLE_TEXT")
    embeddings = await embed_texts([chunk["snippet"] for chunk in chunks])

    file_id: int | None = None
    key: str | None = None
    openai_sync_status = None

    async with SessionLocal() as db:
        try:
            legacy_game_system_tag = await ensure_default_game_system_tag(db)
            resolved_folder_id = await _resolve_upload_folder_id(db, requested_folder_id=folder_id, user_id=user.id)
            selected_ruleset = await _resolve_ruleset(db, requested_ruleset_id=ruleset_id, user_id=user.id)
            selected_tags = await _resolve_general_tags(db, tag_ids=parsed_tag_ids)

            key = f"u/{user.id}/folders/{resolved_folder_id}/{normalized_filename}"
            await _put_file_in_storage(key, data, normalized_mime_type)

            res = await db.execute(
                insert(FileModel)
                .values(
                    {
                        "folder_id": resolved_folder_id,
                        "ruleset_id": selected_ruleset.id,
                        "game_system_tag_id": legacy_game_system_tag.id,
                        "title": normalized_title,
                        "description": normalized_description or None,
                        "filename": normalized_filename,
                        "mime_type": normalized_mime_type,
                        "size_bytes": len(data),
                        "s3_key": key,
                        "is_public": bool(is_public),
                    }
                )
                .returning(FileModel.id)
            )
            file_id = res.scalar_one()

            if selected_tags:
                await db.execute(insert(FileTag), [{"file_id": file_id, "tag_id": tag.id} for tag in selected_tags])

            if settings.OPENAI_VECTOR_STORE_ID and settings.OPENAI_VECTOR_STORE_AUTO_SYNC:
                try:
                    sync_result = await sync_file_to_vector_store(
                        filename=normalized_filename,
                        mime_type=normalized_mime_type,
                        data=data,
                        vector_store_id=settings.OPENAI_VECTOR_STORE_ID,
                        attributes={
                            "app_file_id": file_id,
                            "folder_id": resolved_folder_id,
                            "user_id": user.id,
                            "filename": normalized_filename,
                            "source": "lexmechanicus_upload",
                            "ruleset_id": selected_ruleset.id,
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
                        .values({"openai_vector_store_status": "failed", "openai_last_error": str(exc)[:2000]})
                    )

            for chunk, embedding in zip(chunks, embeddings):
                await db.execute(
                    insert(FileChunk).values(
                        {
                            "file_id": file_id,
                            "start_byte": chunk["start_byte"],
                            "end_byte": chunk["end_byte"],
                            "title": chunk["title"],
                            "section": chunk["section"],
                            "snippet": chunk["snippet"],
                            "embedding": embedding,
                        }
                    )
                )

            await db.commit()
        except IntegrityError:
            await db.rollback()
            if key:
                try:
                    await _delete_file_from_storage(key)
                except Exception:
                    logger.warning("Failed to clean up stored file after integrity error", extra={"key": key})
            raise_api_error(400, "Upload metadata is invalid. The selected folder or related records are missing.", "UPLOAD_METADATA_INVALID")
        except SQLAlchemyError:
            await db.rollback()
            if key:
                try:
                    await _delete_file_from_storage(key)
                except Exception:
                    logger.warning("Failed to clean up stored file after database error", extra={"key": key})
            raise_api_error(503, "The upload could not be saved right now. Please try again.", "UPLOAD_SAVE_FAILED")

    return {
        "status": "ok",
        "file_id": file_id,
        "chunks": len(chunks),
        "openai_vector_store_status": openai_sync_status,
        "game_system": serialize_ruleset(selected_ruleset),
        "tags": [serialize_tag(tag) for tag in selected_tags],
    }


@router.get("/files")
async def list_files(
    scope: str = Query("browse", pattern="^(browse|mine|saved)$"),
    q: str = Query("", max_length=200),
    ruleset_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_optional_user),
):
    if scope in {"mine", "saved"} and user is None:
        raise_api_error(401, "Create an account or sign in to use this feature.", "AUTH_REQUIRED")

    async with SessionLocal() as db:
        try:
            _, scoped_ruleset_ids = await get_ruleset_scope_ids(db, ruleset_id=ruleset_id)
            if ruleset_id is not None and scoped_ruleset_ids == []:
                raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")

            chunk_counts = select(FileChunk.file_id, func.count().label("chunk_count")).group_by(FileChunk.file_id).subquery()
            save_counts = select(SavedFile.file_id, func.count().label("save_count")).group_by(SavedFile.file_id).subquery()
            stmt = (
                select(
                    FileModel.id,
                    FileModel.title,
                    FileModel.description,
                    FileModel.filename,
                    FileModel.mime_type,
                    FileModel.size_bytes,
                    FileModel.is_public,
                    FileModel.openai_vector_store_status,
                    FileModel.ruleset_id,
                    Folder.id.label("folder_id"),
                    User.display_name.label("uploader_display_name"),
                    chunk_counts.c.chunk_count,
                    save_counts.c.save_count,
                )
                .join(Folder, Folder.id == FileModel.folder_id)
                .join(User, User.id == Folder.user_id)
                .outerjoin(chunk_counts, chunk_counts.c.file_id == FileModel.id)
                .outerjoin(save_counts, save_counts.c.file_id == FileModel.id)
                .order_by(FileModel.id.desc())
                .limit(limit)
            )

            if scope == "mine":
                stmt = stmt.where(Folder.user_id == user.id)
            elif scope == "saved":
                stmt = (
                    stmt.join(SavedFile, SavedFile.file_id == FileModel.id)
                    .where(
                        SavedFile.user_id == user.id,
                        build_file_access_condition(user_id=user.id),
                    )
                )
            else:
                if user is not None:
                    stmt = stmt.where(build_file_access_condition(user_id=user.id))
                else:
                    stmt = stmt.where(FileModel.is_public.is_(True))

            if scoped_ruleset_ids is not None:
                stmt = stmt.where(FileModel.ruleset_id.in_(scoped_ruleset_ids))

            normalized_q = q.strip().lower()
            if normalized_q:
                tag_name_match = (
                    select(FileTag.file_id)
                    .join(Tag, Tag.id == FileTag.tag_id)
                    .where(FileTag.file_id == FileModel.id, func.lower(Tag.name).like(f"%{normalized_q}%"))
                    .exists()
                )
                ruleset_name_match = (
                    select(Ruleset.id)
                    .where(Ruleset.id == FileModel.ruleset_id, func.lower(Ruleset.name).like(f"%{normalized_q}%"))
                    .exists()
                )
                ruleset_alias_match = (
                    select(RulesetAlias.id)
                    .where(
                        RulesetAlias.ruleset_id == FileModel.ruleset_id,
                        RulesetAlias.normalized_alias.like(f"%{normalized_q}%"),
                    )
                    .exists()
                )
                stmt = stmt.where(
                    or_(
                        func.lower(FileModel.title).like(f"%{normalized_q}%"),
                        func.lower(func.coalesce(FileModel.description, "")).like(f"%{normalized_q}%"),
                        func.lower(FileModel.filename).like(f"%{normalized_q}%"),
                        func.cast(FileModel.id, Text) == normalized_q,
                        tag_name_match,
                        ruleset_name_match,
                        ruleset_alias_match,
                    )
                )

            rows = (await db.execute(stmt)).mappings().all()
            file_ids = [row["id"] for row in rows]
            rulesets, tags_by_file = await _serialize_file_metadata(db, file_ids)
            saved_file_ids = set(file_ids) if scope == "saved" and user is not None else await _load_saved_file_ids(
                db,
                user_id=user.id if user else None,
                file_ids=file_ids,
            )
        except SQLAlchemyError:
            logger.exception("File listing failed", extra={"scope": scope, "user_id": user.id if user else None, "ruleset_id": ruleset_id})
            raise_api_error(503, "The file list is temporarily unavailable. Please try again.", "FILE_LIST_UNAVAILABLE")

    return [
        _serialize_file_listing_row(
            row,
            rulesets=rulesets,
            tags_by_file=tags_by_file,
            saved_file_ids=saved_file_ids,
        )
        for row in rows
    ]


@router.post("/{file_id}/saved")
async def save_file(file_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            await _load_accessible_file(db, file_id=file_id, user_id=user.id)
            existing = await db.scalar(
                select(SavedFile.id).where(
                    SavedFile.user_id == user.id,
                    SavedFile.file_id == file_id,
                )
            )
            if existing is None:
                db.add(SavedFile(user_id=user.id, file_id=file_id))
                await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file could not be saved right now.", "FILE_SAVE_FAILED")
    return {"saved": True}


@router.delete("/{file_id}/saved")
async def unsave_file(file_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            await db.execute(
                delete(SavedFile).where(
                    SavedFile.user_id == user.id,
                    SavedFile.file_id == file_id,
                )
            )
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file could not be unsaved right now.", "FILE_UNSAVE_FAILED")
    return {"saved": False}


@router.put("/{file_id}/tags")
async def update_file_tags(file_id: int, body: FileTagsUpdateRequest, user=Depends(get_current_user)):
    normalized_tag_ids = _parse_tag_ids(json.dumps(body.tag_ids))
    async with SessionLocal() as db:
        try:
            await _load_owned_file(db, file_id=file_id, user_id=user.id)
            tags = await _resolve_general_tags(db, tag_ids=normalized_tag_ids)
            await db.execute(delete(FileTag).where(FileTag.file_id == file_id))
            if tags:
                await db.execute(insert(FileTag), [{"file_id": file_id, "tag_id": tag.id} for tag in tags])
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file tags could not be updated right now.", "FILE_TAG_UPDATE_FAILED")
    return {"tags": [serialize_tag(tag) for tag in tags]}


@router.put("/{file_id}/title")
async def update_file_title(file_id: int, body: FileTitleUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            file_model = await _load_owned_file(db, file_id=file_id, user_id=user.id)
            file_model.title = body.title
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file title could not be updated right now.", "FILE_TITLE_UPDATE_FAILED")
    return {"title": body.title}


@router.put("/{file_id}/game-system")
async def update_file_game_system(file_id: int, body: FileGameSystemUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            file_model = await _load_owned_file(db, file_id=file_id, user_id=user.id)
            selected_ruleset = await _resolve_ruleset(db, requested_ruleset_id=body.ruleset_id, user_id=user.id)
            file_model.ruleset_id = selected_ruleset.id
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file game system could not be updated right now.", "FILE_GAME_SYSTEM_UPDATE_FAILED")
    return {"game_system": serialize_ruleset(selected_ruleset)}


@router.delete("/{file_id}")
async def delete_file(file_id: int, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            file_row = await db.execute(
                select(FileModel, Folder.user_id).join(Folder, Folder.id == FileModel.folder_id).where(FileModel.id == file_id)
            )
            record = file_row.first()
            if not record:
                raise_api_error(404, "File not found.", "FILE_NOT_FOUND")
            file_model, owner_id = record
            if owner_id != user.id:
                raise_api_error(403, "You do not have permission to delete this file.", "FILE_DELETE_FORBIDDEN")
            await _delete_file_from_storage(file_model.s3_key)
            await db.execute(delete(FileModel).where(FileModel.id == file_id))
            await _delete_empty_bundles_for_file(db, file_id=file_id)
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(503, "The file could not be deleted right now. Please try again.", "FILE_DELETE_FAILED")
    return {"status": "ok"}
