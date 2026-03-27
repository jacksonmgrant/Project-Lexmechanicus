from __future__ import annotations

from sqlalchemy import text
from ..db import SessionLocal


# Speed-first: do BM25-like FTS by ts_rank + optional vector rerank in SQL.


HYBRID_SQL = """
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.title, fc.section, fc.snippet,
        ts_rank_cd(to_tsvector('english', fc.snippet), websearch_to_tsquery('english', :query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    WHERE to_tsvector('english', fc.snippet) @@ websearch_to_tsquery('english', :query)
        AND f.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND f.is_public = TRUE)
            OR (
                :user_id IS NOT NULL AND (
                    fo.user_id = :user_id
                    OR EXISTS (
                        SELECT 1
                        FROM marketplace_packs mp
                        JOIN saved_packs sp ON sp.marketplace_pack_id = mp.id
                        WHERE
                            mp.folder_id = f.folder_id
                            AND sp.user_id = :user_id
                    )
                )
            )
        )
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


async def hybrid_retrieve(user_id: int | None, *, ruleset_ids: list[int], include_all: bool, query: str, k: int = 12):
    normalized_query = query.strip()
    if not normalized_query:
        return []
    if include_all or len(ruleset_ids) != 1:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(HYBRID_SQL),
                {
                    "query": normalized_query,
                    "ruleset_id": ruleset_ids[0],
                    "user_id": user_id,
                    "k": k,
                },
            )
        ).mappings().all()
        # Vector rerank can be skipped for speed if needed.
        return [dict(r) for r in rows]
