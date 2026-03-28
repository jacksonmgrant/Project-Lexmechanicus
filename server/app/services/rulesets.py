from __future__ import annotations

import re

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import File as FileModel
from ..models import Folder, MarketplacePack, Ruleset, RulesetAlias, SavedPack, User

DEFAULT_RULESET_NAME = "All Systems"
DEFAULT_RULESET_SLUG = "all-systems"


def normalize_ruleset_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    lowered = collapsed.lower()
    return lowered[:160]


def slugify_ruleset_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:160] or DEFAULT_RULESET_SLUG


def serialize_ruleset(ruleset: Ruleset | None) -> dict[str, object] | None:
    if ruleset is None:
        return None
    return {
        "id": ruleset.id,
        "name": ruleset.name,
        "slug": ruleset.slug,
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


async def ensure_default_ruleset(db: AsyncSession) -> Ruleset:
    existing = await db.scalar(select(Ruleset).where(Ruleset.slug == DEFAULT_RULESET_SLUG))
    if existing is not None:
        if existing.name != DEFAULT_RULESET_NAME:
            existing.name = DEFAULT_RULESET_NAME
        if existing.normalized_name != normalize_ruleset_text(DEFAULT_RULESET_NAME):
            existing.normalized_name = normalize_ruleset_text(DEFAULT_RULESET_NAME)
        if existing.kind != "general":
            existing.kind = "general"
        existing.parent_id = None
        existing.edition_label = None
        return existing

    ruleset = Ruleset(
        name=DEFAULT_RULESET_NAME,
        normalized_name=normalize_ruleset_text(DEFAULT_RULESET_NAME),
        slug=DEFAULT_RULESET_SLUG,
        kind="general",
    )
    db.add(ruleset)
    await db.flush()
    await ensure_ruleset_aliases(db, ruleset=ruleset, aliases=[DEFAULT_RULESET_NAME])
    return ruleset


async def ensure_ruleset_aliases(db: AsyncSession, *, ruleset: Ruleset, aliases: list[str]) -> None:
    seen: set[str] = set()
    for alias in aliases:
        cleaned_alias = re.sub(r"\s+", " ", alias.strip())[:160]
        if not cleaned_alias:
            continue
        normalized_alias = normalize_ruleset_text(cleaned_alias)
        if normalized_alias in seen:
            continue
        seen.add(normalized_alias)
        existing = await db.scalar(select(RulesetAlias).where(RulesetAlias.normalized_alias == normalized_alias))
        if existing is not None:
            if existing.ruleset_id != ruleset.id:
                raise ValueError(f'"{cleaned_alias}" already belongs to another ruleset.')
            continue
        db.add(
            RulesetAlias(
                ruleset_id=ruleset.id,
                alias=cleaned_alias,
                normalized_alias=normalized_alias,
            )
        )
    await db.flush()


async def get_rulesets_by_ids(db: AsyncSession, *, ids: list[int]) -> list[Ruleset]:
    if not ids:
        return []
    rulesets = (await db.execute(select(Ruleset).where(Ruleset.id.in_(ids)).order_by(func.lower(Ruleset.name), Ruleset.id))).scalars().all()
    by_id = {ruleset.id: ruleset for ruleset in rulesets}
    return [by_id[ruleset_id] for ruleset_id in ids if ruleset_id in by_id]


async def search_rulesets(db: AsyncSession, *, query: str, limit: int = 12) -> list[Ruleset]:
    normalized_query = normalize_ruleset_text(query)
    if not normalized_query:
        stmt: Select[tuple[Ruleset]] = select(Ruleset).order_by(func.lower(Ruleset.name), Ruleset.id).limit(limit)
        return (await db.execute(stmt)).scalars().all()

    matching_ids = (
        await db.execute(
            select(Ruleset.id)
            .outerjoin(RulesetAlias, RulesetAlias.ruleset_id == Ruleset.id)
            .where(
                or_(
                    func.lower(Ruleset.name).like(f"%{normalized_query}%"),
                    RulesetAlias.normalized_alias.like(f"%{normalized_query}%"),
                )
            )
            .group_by(Ruleset.id, Ruleset.name)
            .order_by(func.lower(Ruleset.name), Ruleset.id)
            .limit(limit)
        )
    ).scalars().all()
    return await get_rulesets_by_ids(db, ids=matching_ids)


async def create_ruleset(
    db: AsyncSession,
    *,
    name: str,
    aliases: list[str],
) -> Ruleset:
    display_name = re.sub(r"\s+", " ", name.strip())
    if not display_name:
        raise ValueError("Enter a game system name.")

    normalized_display_name = normalize_ruleset_text(display_name)
    existing = await db.scalar(select(Ruleset).where(Ruleset.normalized_name == normalized_display_name))
    if existing is not None:
        raise ValueError(f'"{existing.name}" already exists.')

    slug_base = slugify_ruleset_name(display_name)
    slug = slug_base
    suffix = 2
    while await db.scalar(select(Ruleset.id).where(Ruleset.slug == slug)):
        slug = f"{slug_base}-{suffix}"
        suffix += 1

    ruleset = Ruleset(
        name=display_name,
        normalized_name=normalized_display_name,
        slug=slug,
        kind="general",
        parent_id=None,
        edition_label=None,
    )
    db.add(ruleset)
    await db.flush()
    await ensure_ruleset_aliases(db, ruleset=ruleset, aliases=[display_name, *aliases])
    return ruleset


async def get_ruleset_scope_ids(db: AsyncSession, *, ruleset_id: int | None) -> tuple[Ruleset | None, list[int] | None]:
    if ruleset_id is None:
        return None, None

    ruleset = await db.get(Ruleset, ruleset_id)
    if ruleset is None:
        return None, []
    return ruleset, [ruleset.id]


async def list_user_rulesets(db: AsyncSession, *, user_id: int | None) -> list[Ruleset]:
    accessible_ruleset_ids = select(FileModel.ruleset_id).join(Folder, Folder.id == FileModel.folder_id).where(FileModel.ruleset_id.is_not(None))
    if user_id is None:
        accessible_ruleset_ids = accessible_ruleset_ids.where(FileModel.is_public.is_(True)).distinct()
    else:
        # Keep the authenticated dropdown aligned with browse access so public
        # rules stay visible even for users who have not uploaded anything yet.
        accessible_ruleset_ids = accessible_ruleset_ids.where(build_file_access_condition(user_id=user_id)).distinct()

    available_rulesets = (
        await db.execute(
            select(Ruleset)
            .where(Ruleset.id.in_(accessible_ruleset_ids))
            .order_by(func.lower(Ruleset.name), Ruleset.id)
        )
    ).scalars().all()

    if user_id is None:
        return available_rulesets

    owned_usage_rows = (
        await db.execute(
            select(FileModel.ruleset_id, func.count(FileModel.id))
            .join(Folder, Folder.id == FileModel.folder_id)
            .where(
                Folder.user_id == user_id,
                FileModel.ruleset_id.is_not(None),
            )
            .group_by(FileModel.ruleset_id)
        )
    ).all()
    usage_by_ruleset_id = {ruleset_id: count for ruleset_id, count in owned_usage_rows if ruleset_id is not None}
    available_rulesets.sort(key=lambda ruleset: (-usage_by_ruleset_id.get(ruleset.id, 0), ruleset.name.lower(), ruleset.id))
    return available_rulesets


async def get_active_ruleset(db: AsyncSession, *, user_id: int | None) -> tuple[Ruleset | None, list[Ruleset]]:
    available_rulesets = await list_user_rulesets(db, user_id=user_id)
    available_ruleset_ids = {ruleset.id for ruleset in available_rulesets}

    if user_id is None:
        active_ruleset = available_rulesets[0] if available_rulesets else None
        return active_ruleset, available_rulesets

    user = await db.get(User, user_id)
    if user is None:
        active_ruleset = available_rulesets[0] if available_rulesets else None
        return active_ruleset, available_rulesets

    if user.active_ruleset_id in available_ruleset_ids:
        active_ruleset = next(ruleset for ruleset in available_rulesets if ruleset.id == user.active_ruleset_id)
        return active_ruleset, available_rulesets

    if user.active_ruleset_id is not None:
        active_ruleset = await db.get(Ruleset, user.active_ruleset_id)
        if active_ruleset is not None:
            extra_rulesets = [ruleset for ruleset in available_rulesets if ruleset.id != active_ruleset.id]
            return active_ruleset, [active_ruleset, *extra_rulesets]

    if available_rulesets:
        user.active_ruleset_id = available_rulesets[0].id
        await db.flush()
        return available_rulesets[0], available_rulesets

    user.active_ruleset_id = None
    await db.flush()
    return None, []
