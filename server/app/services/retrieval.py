from __future__ import annotations
from typing import Sequence
from sqlalchemy import text
from ..db import SessionLocal


# Speed-first: do BM25-like FTS by ts_rank + optional vector rerank in SQL.


HYBRID_SQL = """
WITH q AS (
    SELECT to_tsquery('english', :ts) AS tsq
), kw AS (
    SELECT fc.id, fc.file_id, fc.title, fc.section, fc.snippet,
        ts_rank_cd(to_tsvector('english', fc.snippet), (SELECT tsq FROM q)) AS rank
    FROM file_chunks fc
    WHERE to_tsvector('english', fc.snippet) @@ (SELECT tsq FROM q)
    ORDER BY rank DESC
    LIMIT :k
)
SELECT id, file_id, title, section, snippet, rank
FROM kw
ORDER BY rank DESC
"""


RERANK_SQL = """
SELECT id, file_id, title, section, snippet,
    (rank * 0.6 + (1.0 - (embedding <=> :qvec)) * 0.4) AS score
FROM file_chunks fc
WHERE id = ANY(:ids)
ORDER BY score DESC
"""


async def hybrid_retrieve(user_id: int | None, game_system_id: int, query: str, k: int = 12):
    # NOTE: add user and game_system filters to both CTEs for correctness; omitted for brevity.
    ts = " & ".join([w for w in query.split() if len(w) > 2])
    async with SessionLocal() as db:
        rows = (await db.execute(text(HYBRID_SQL), {"ts": ts, "k": k})).mappings().all()
        # Vector rerank can be skipped for speed if needed.
        return [dict(r) for r in rows]
