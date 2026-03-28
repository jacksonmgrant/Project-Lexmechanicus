from __future__ import annotations

import re

from sqlalchemy import Integer, String, bindparam, text
from ..db import SessionLocal


# Speed-first: do BM25-like FTS by ts_rank + optional vector rerank in SQL.


HYBRID_SQL = """
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
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
                    f.is_public = TRUE
                    OR
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
SELECT id, file_id, start_byte, end_byte, title, section, snippet, rank
FROM kw
ORDER BY rank DESC
"""


FALLBACK_HYBRID_SQL = """
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        ts_rank_cd(to_tsvector('english', fc.snippet), to_tsquery('english', :fallback_query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    WHERE to_tsvector('english', fc.snippet) @@ to_tsquery('english', :fallback_query)
        AND f.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND f.is_public = TRUE)
            OR (
                :user_id IS NOT NULL AND (
                    f.is_public = TRUE
                    OR
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
SELECT id, file_id, start_byte, end_byte, title, section, snippet, rank
FROM kw
ORDER BY rank DESC
"""


FILTERED_BUNDLE_SQL = """
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        ts_rank_cd(to_tsvector('english', fc.snippet), websearch_to_tsquery('english', :query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    JOIN bundle_files bf ON bf.file_id = f.id
    JOIN bundles b ON b.id = bf.bundle_id
    WHERE to_tsvector('english', fc.snippet) @@ websearch_to_tsquery('english', :query)
        AND f.ruleset_id = :ruleset_id
        AND b.id = :bundle_id
        AND b.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND b.is_public = TRUE AND f.is_public = TRUE)
            OR (
                :user_id IS NOT NULL AND (
                    b.owner_id = :user_id
                    OR b.is_public = TRUE
                )
                AND (
                    f.is_public = TRUE
                    OR fo.user_id = :user_id
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
SELECT id, file_id, start_byte, end_byte, title, section, snippet, rank
FROM kw
ORDER BY rank DESC
"""


FALLBACK_FILTERED_BUNDLE_SQL = """
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        ts_rank_cd(to_tsvector('english', fc.snippet), to_tsquery('english', :fallback_query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    JOIN bundle_files bf ON bf.file_id = f.id
    JOIN bundles b ON b.id = bf.bundle_id
    WHERE to_tsvector('english', fc.snippet) @@ to_tsquery('english', :fallback_query)
        AND f.ruleset_id = :ruleset_id
        AND b.id = :bundle_id
        AND b.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND b.is_public = TRUE AND f.is_public = TRUE)
            OR (
                :user_id IS NOT NULL AND (
                    b.owner_id = :user_id
                    OR b.is_public = TRUE
                )
                AND (
                    f.is_public = TRUE
                    OR fo.user_id = :user_id
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
SELECT id, file_id, start_byte, end_byte, title, section, snippet, rank
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


HYBRID_QUERY = text(HYBRID_SQL).bindparams(
    bindparam("query", type_=String()),
    bindparam("ruleset_id", type_=Integer()),
    bindparam("user_id", type_=Integer()),
    bindparam("k", type_=Integer()),
)


FILTERED_BUNDLE_QUERY = text(FILTERED_BUNDLE_SQL).bindparams(
    bindparam("query", type_=String()),
    bindparam("ruleset_id", type_=Integer()),
    bindparam("user_id", type_=Integer()),
    bindparam("bundle_id", type_=Integer()),
    bindparam("k", type_=Integer()),
)


FALLBACK_HYBRID_QUERY = text(FALLBACK_HYBRID_SQL).bindparams(
    bindparam("fallback_query", type_=String()),
    bindparam("ruleset_id", type_=Integer()),
    bindparam("user_id", type_=Integer()),
    bindparam("k", type_=Integer()),
)


FALLBACK_FILTERED_BUNDLE_QUERY = text(FALLBACK_FILTERED_BUNDLE_SQL).bindparams(
    bindparam("fallback_query", type_=String()),
    bindparam("ruleset_id", type_=Integer()),
    bindparam("user_id", type_=Integer()),
    bindparam("bundle_id", type_=Integer()),
    bindparam("k", type_=Integer()),
)


QUESTION_STOPWORDS = {
    "a", "an", "and", "are", "be", "can", "could", "did", "do", "does", "for",
    "from", "how", "i", "if", "in", "is", "it", "me", "my", "of", "on", "or",
    "should", "tell", "that", "the", "their", "there", "these", "this", "to",
    "what", "when", "where", "which", "who", "why", "with", "would", "you", "your",
}


def _build_fallback_query(query: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9\\-\\s]+", " ", query.lower()).replace("-", " ")
    terms: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        if token in QUESTION_STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    if not terms:
        return None
    return " | ".join(terms[:8])


async def hybrid_retrieve(
    user_id: int | None,
    *,
    ruleset_ids: list[int],
    include_all: bool,
    query: str,
    k: int = 12,
    bundle_id: int | None = None,
):
    normalized_query = query.strip()
    if not normalized_query:
        return []
    if include_all or len(ruleset_ids) != 1:
        return []
    async with SessionLocal() as db:
        sql = FILTERED_BUNDLE_QUERY if bundle_id is not None else HYBRID_QUERY
        params = {
            "query": normalized_query,
            "ruleset_id": ruleset_ids[0],
            "user_id": user_id,
            "k": k,
        }
        if bundle_id is not None:
            params["bundle_id"] = bundle_id
        rows = (
            await db.execute(
                sql,
                params,
            )
        ).mappings().all()
        if rows:
            return [dict(r) for r in rows]

        fallback_query = _build_fallback_query(normalized_query)
        if not fallback_query:
            return []

        fallback_sql = FALLBACK_FILTERED_BUNDLE_QUERY if bundle_id is not None else FALLBACK_HYBRID_QUERY
        fallback_params = {
            "fallback_query": fallback_query,
            "ruleset_id": ruleset_ids[0],
            "user_id": user_id,
            "k": k,
        }
        if bundle_id is not None:
            fallback_params["bundle_id"] = bundle_id
        rows = (
            await db.execute(
                fallback_sql,
                fallback_params,
            )
        ).mappings().all()
        # Vector rerank can be skipped for speed if needed.
        return [dict(r) for r in rows]
