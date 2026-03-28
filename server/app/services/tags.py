from __future__ import annotations

import re

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import File as FileModel
from ..models import Folder, MarketplacePack, SavedPack, Tag, User


GENERAL_TAG_KIND = "general"
GAME_SYSTEM_TAG_KIND = "game_system"
DEFAULT_GAME_SYSTEM_NAME = "All Systems"
DEFAULT_GAME_SYSTEM_SLUG = "general-rules"


def slugify_tag_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or DEFAULT_GAME_SYSTEM_SLUG


def normalize_tag_name(name: str) -> str:
    collapsed = re.sub(r"\s+", " ", name.strip())
    return collapsed[:120]


def serialize_tag(tag: Tag | None) -> dict[str, object] | None:
    if tag is None:
        return None
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "kind": tag.kind,
    }


def _saved_pack_folder_exists(user_id: int):
    return (
        select(MarketplacePack.id)
        .join(SavedPack, SavedPack.marketplace_pack_id == MarketplacePack.id)
        .where(
            MarketplacePack.folder_id == FileModel.folder_id,
            SavedPack.user_id == user_id,
        )
        .exists()
    )


def build_file_access_condition(*, user_id: int | None, include_public_for_authenticated: bool = True):
    if user_id is None:
        return FileModel.is_public.is_(True)

    access_clauses = [Folder.user_id == user_id, _saved_pack_folder_exists(user_id)]
    if include_public_for_authenticated:
        access_clauses.insert(0, FileModel.is_public.is_(True))
    return or_(*access_clauses)


async def ensure_default_game_system_tag(db: AsyncSession) -> Tag:
    existing = await db.scalar(select(Tag).where(Tag.slug == DEFAULT_GAME_SYSTEM_SLUG))
    if existing is not None:
        if existing.kind != GAME_SYSTEM_TAG_KIND:
            existing.kind = GAME_SYSTEM_TAG_KIND
        if existing.name != DEFAULT_GAME_SYSTEM_NAME:
            existing.name = DEFAULT_GAME_SYSTEM_NAME
        return existing

    tag = Tag(
        name=DEFAULT_GAME_SYSTEM_NAME,
        slug=DEFAULT_GAME_SYSTEM_SLUG,
        kind=GAME_SYSTEM_TAG_KIND,
    )
    db.add(tag)
    await db.flush()
    return tag


async def get_or_create_tag(db: AsyncSession, *, name: str, kind: str) -> Tag:
    normalized_name = normalize_tag_name(name)
    if not normalized_name:
        raise ValueError("Tag names cannot be blank.")

    slug = slugify_tag_name(normalized_name)
    existing = await db.scalar(select(Tag).where(Tag.slug == slug))
    if existing is not None:
        if existing.kind != kind:
            raise ValueError(f'"{existing.name}" already exists as a different tag type.')
        if existing.name != normalized_name:
            existing.name = normalized_name
        return existing

    tag = Tag(name=normalized_name, slug=slug, kind=kind)
    db.add(tag)
    await db.flush()
    return tag


async def get_tags_by_ids(db: AsyncSession, *, ids: list[int], kind: str | None = None) -> list[Tag]:
    if not ids:
        return []

    stmt: Select[tuple[Tag]] = select(Tag).where(Tag.id.in_(ids))
    if kind is not None:
        stmt = stmt.where(Tag.kind == kind)
    tags = (await db.execute(stmt.order_by(func.lower(Tag.name), Tag.id))).scalars().all()
    tags_by_id = {tag.id: tag for tag in tags}
    return [tags_by_id[tag_id] for tag_id in ids if tag_id in tags_by_id]


async def list_user_game_system_tags(db: AsyncSession, *, user_id: int | None) -> list[Tag]:
    default_tag = await ensure_default_game_system_tag(db)
    if user_id is None:
        return [default_tag]

    accessible_tag_ids = (
        select(FileModel.game_system_tag_id)
        .join(Folder, Folder.id == FileModel.folder_id)
        .where(build_file_access_condition(user_id=user_id, include_public_for_authenticated=False))
        .distinct()
    )

    stmt = (
        select(Tag)
        .where(
            Tag.kind == GAME_SYSTEM_TAG_KIND,
            Tag.id.in_(accessible_tag_ids),
        )
        .order_by(func.lower(Tag.name), Tag.id)
    )
    tags = (await db.execute(stmt)).scalars().all()
    if not any(tag.id == default_tag.id for tag in tags):
        tags.insert(0, default_tag)
    return tags


async def get_active_game_system(db: AsyncSession, *, user_id: int | None) -> tuple[Tag, list[Tag]]:
    available_tags = await list_user_game_system_tags(db, user_id=user_id)
    available_tag_ids = {tag.id for tag in available_tags}
    default_tag = next((tag for tag in available_tags if tag.slug == DEFAULT_GAME_SYSTEM_SLUG), available_tags[0])

    if user_id is None:
        return default_tag, available_tags

    user = await db.get(User, user_id)
    if user is None:
        return default_tag, available_tags

    if user.active_game_system_tag_id in available_tag_ids:
        active_tag = next(tag for tag in available_tags if tag.id == user.active_game_system_tag_id)
        return active_tag, available_tags

    if user.active_game_system_tag_id is not None:
        active_tag = await db.get(Tag, user.active_game_system_tag_id)
        if active_tag is not None and active_tag.kind == GAME_SYSTEM_TAG_KIND:
            return active_tag, [active_tag, *available_tags]

    user.active_game_system_tag_id = default_tag.id
    await db.flush()
    return default_tag, available_tags


async def search_tags(db: AsyncSession, *, query: str, kind: str | None, limit: int = 12) -> list[Tag]:
    stmt = select(Tag)
    normalized_query = normalize_tag_name(query)
    if normalized_query:
        stmt = stmt.where(func.lower(Tag.name).like(f"%{normalized_query.lower()}%"))
    if kind:
        stmt = stmt.where(Tag.kind == kind)
    stmt = stmt.order_by(func.lower(Tag.name), Tag.id).limit(limit)
    return (await db.execute(stmt)).scalars().all()
