from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, String, bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from ..auth import get_optional_user
from ..db import SessionLocal
from ..errors import raise_api_error
from ..services.rulesets import get_ruleset_scope_ids


router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


SQL = """
SELECT fc.id, fc.file_id, fc.title, fc.section,
    substring(fc.snippet from 1 for 240) AS preview,
    0.0::float AS score
FROM file_chunks fc
WHERE to_tsvector('english', fc.snippet) @@ websearch_to_tsquery('english', :q)
AND EXISTS (
    SELECT 1
    FROM files f
    JOIN folders fo ON f.folder_id = fo.id
    WHERE
        f.id = fc.file_id
        AND f.ruleset_id = :ruleset_id
        AND (
            (f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
            OR (:user_id IS NOT NULL AND fo.user_id = :user_id)
        )
)
LIMIT 20
"""


SEARCH_QUERY = text(SQL).bindparams(
    bindparam("q", type_=String()),
    bindparam("ruleset_id", type_=Integer()),
    bindparam("user_id", type_=Integer()),
)


@router.get("")
async def search(q: str = Query(..., min_length=1, max_length=200), ruleset_id: int = Query(..., ge=1), user=Depends(get_optional_user)):
    normalized_query = q.strip()
    if not normalized_query:
        raise_api_error(422, "Enter a search query before searching.", "SEARCH_QUERY_REQUIRED")

    async with SessionLocal() as db:
        try:
            _, scoped_ruleset_ids = await get_ruleset_scope_ids(db, ruleset_id=ruleset_id)
            if scoped_ruleset_ids == []:
                raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")
            if scoped_ruleset_ids is None:
                raise_api_error(422, "Choose a game system before searching.", "RULESET_REQUIRED")
            rows = (
                await db.execute(
                    SEARCH_QUERY,
                    {
                        "q": normalized_query,
                        "ruleset_id": scoped_ruleset_ids[0],
                        "user_id": user.id if user else None,
                    },
                )
            ).mappings().all()
        except SQLAlchemyError:
            logger.exception(
                "Search request failed",
                extra={"ruleset_id": ruleset_id, "user_id": user.id if user else None},
            )
            raise_api_error(503, "Search is temporarily unavailable. Please try again.", "SEARCH_UNAVAILABLE")
        return [dict(r) for r in rows]
