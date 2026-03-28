from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Bundle, BundleFile, Ruleset, SavedBundle, User, UserRulesetBundle
from .rulesets import serialize_ruleset


def build_bundle_access_condition(*, user_id: int | None, include_public_for_authenticated: bool = True):
    if user_id is None:
        return Bundle.is_public.is_(True)

    access_clauses = [Bundle.owner_id == user_id]
    if include_public_for_authenticated:
        access_clauses.insert(0, Bundle.is_public.is_(True))
    return or_(*access_clauses)


def serialize_bundle(
    bundle: Bundle,
    *,
    ruleset: Ruleset | None = None,
    owner: User | None = None,
    file_count: int = 0,
    save_count: int = 0,
    is_saved: bool = False,
    is_default: bool = False,
    preview_titles: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": bundle.id,
        "title": bundle.title,
        "description": bundle.description,
        "is_public": bundle.is_public,
        "is_saved": is_saved,
        "is_default": is_default,
        "is_owned": owner is not None and owner.id == bundle.owner_id,
        "file_count": file_count,
        "save_count": save_count,
        "game_system": serialize_ruleset(ruleset),
        "game_system_id": bundle.ruleset_id,
        "owner_name": (owner.display_name or "Anonymous") if owner is not None else "",
        "preview_titles": preview_titles or [],
        "created_at": bundle.created_at.isoformat() if bundle.created_at else None,
    }


async def get_active_bundle_for_ruleset(db: AsyncSession, *, user_id: int | None, ruleset_id: int | None) -> Bundle | None:
    if user_id is None or ruleset_id is None:
        return None

    return await db.scalar(
        select(Bundle)
        .join(UserRulesetBundle, UserRulesetBundle.bundle_id == Bundle.id)
        .where(
            UserRulesetBundle.user_id == user_id,
            UserRulesetBundle.ruleset_id == ruleset_id,
            build_bundle_access_condition(user_id=user_id),
        )
        .limit(1)
    )


async def get_saved_bundle_ids(db: AsyncSession, *, user_id: int | None, bundle_ids: list[int]) -> set[int]:
    if user_id is None or not bundle_ids:
        return set()
    rows = await db.execute(
        select(SavedBundle.bundle_id).where(
            SavedBundle.user_id == user_id,
            SavedBundle.bundle_id.in_(bundle_ids),
        )
    )
    return set(rows.scalars().all())


async def get_default_bundle_ids(db: AsyncSession, *, user_id: int | None, bundle_ids: list[int]) -> set[int]:
    if user_id is None or not bundle_ids:
        return set()
    rows = await db.execute(
        select(UserRulesetBundle.bundle_id).where(
            UserRulesetBundle.user_id == user_id,
            UserRulesetBundle.bundle_id.in_(bundle_ids),
        )
    )
    return set(rows.scalars().all())


async def load_accessible_bundle(db: AsyncSession, *, bundle_id: int, user_id: int | None, ruleset_id: int | None = None) -> Bundle | None:
    stmt = select(Bundle).where(Bundle.id == bundle_id, build_bundle_access_condition(user_id=user_id))
    if ruleset_id is not None:
        stmt = stmt.where(Bundle.ruleset_id == ruleset_id)
    return await db.scalar(stmt.limit(1))


async def get_bundle_file_count(db: AsyncSession, *, bundle_id: int) -> int:
    count = await db.scalar(select(func.count(BundleFile.file_id)).where(BundleFile.bundle_id == bundle_id))
    return int(count or 0)
