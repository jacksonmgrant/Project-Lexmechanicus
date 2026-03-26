from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from ..auth import get_current_user
from ..db import SessionLocal


router = APIRouter(prefix="/search", tags=["search"])


SQL = """
SELECT fc.id, fc.file_id, fc.title, fc.section,
    substring(fc.snippet from 1 for 240) AS preview,
    0.0::float AS score
FROM file_chunks fc
-- TODO: add joins to filter by user ownership OR public + saved
WHERE to_tsvector('english', fc.snippet) @@ websearch_to_tsquery('english', :q)
AND EXISTS (
    SELECT 1 FROM files f JOIN folders fo ON f.folder_id = fo.id
    WHERE f.id = fc.file_id AND fo.game_system_id = :gsid
)
LIMIT 20
"""


@router.get("")
async def search(q: str = Query(..., max_length=200), game_system_id: int = Query(...), user=Depends(get_current_user)):
    async with SessionLocal() as db:
        rows = (await db.execute(text(SQL), {"q": q, "gsid": game_system_id})).mappings().all()
        return [dict(r) for r in rows]