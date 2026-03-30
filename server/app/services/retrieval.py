from __future__ import annotations

import re

from sqlalchemy import Integer, String, bindparam, text
from ..db import SessionLocal


# Speed-first: do BM25-like FTS by ts_rank + optional vector rerank in SQL.


SEARCH_VECTOR_SQL = """
    setweight(to_tsvector('english', coalesce(fc.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(fc.section, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(f.title, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(fc.snippet, '')), 'C')
"""


SOURCE_TITLE_SQL = "COALESCE(NULLIF(fc.title, ''), NULLIF(fc.section, ''), NULLIF(f.title, ''), f.filename)"


HYBRID_SQL = f"""
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        f.title AS file_title,
        f.filename,
        {SOURCE_TITLE_SQL} AS source_title,
        ts_rank_cd(({SEARCH_VECTOR_SQL}), websearch_to_tsquery('english', :query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    WHERE ({SEARCH_VECTOR_SQL}) @@ websearch_to_tsquery('english', :query)
        AND f.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
            OR (
                :user_id IS NOT NULL AND (
                    (f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
                    OR
                    fo.user_id = :user_id
                    OR (
                        COALESCE(f.is_copyright_restricted, FALSE) = FALSE
                        AND EXISTS (
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
        )
    ORDER BY rank DESC
    LIMIT :k
)
SELECT id, file_id, start_byte, end_byte, title, section, snippet, file_title, filename, source_title, rank
FROM kw
ORDER BY rank DESC
"""


FALLBACK_HYBRID_SQL = f"""
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        f.title AS file_title,
        f.filename,
        {SOURCE_TITLE_SQL} AS source_title,
        ts_rank_cd(({SEARCH_VECTOR_SQL}), to_tsquery('english', :fallback_query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    WHERE ({SEARCH_VECTOR_SQL}) @@ to_tsquery('english', :fallback_query)
        AND f.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
            OR (
                :user_id IS NOT NULL AND (
                    (f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
                    OR
                    fo.user_id = :user_id
                    OR (
                        COALESCE(f.is_copyright_restricted, FALSE) = FALSE
                        AND EXISTS (
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
        )
    ORDER BY rank DESC
    LIMIT :k
)
SELECT id, file_id, start_byte, end_byte, title, section, snippet, file_title, filename, source_title, rank
FROM kw
ORDER BY rank DESC
"""


FILTERED_BUNDLE_SQL = f"""
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        f.title AS file_title,
        f.filename,
        {SOURCE_TITLE_SQL} AS source_title,
        ts_rank_cd(({SEARCH_VECTOR_SQL}), websearch_to_tsquery('english', :query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    JOIN bundle_files bf ON bf.file_id = f.id
    JOIN bundles b ON b.id = bf.bundle_id
    WHERE ({SEARCH_VECTOR_SQL}) @@ websearch_to_tsquery('english', :query)
        AND f.ruleset_id = :ruleset_id
        AND b.id = :bundle_id
        AND b.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND b.is_public = TRUE AND f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
            OR (
                :user_id IS NOT NULL AND (
                    b.owner_id = :user_id
                    OR b.is_public = TRUE
                )
                AND (
                    (f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
                    OR fo.user_id = :user_id
                    OR (
                        COALESCE(f.is_copyright_restricted, FALSE) = FALSE
                        AND EXISTS (
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
        )
    ORDER BY rank DESC
    LIMIT :k
)
SELECT id, file_id, start_byte, end_byte, title, section, snippet, file_title, filename, source_title, rank
FROM kw
ORDER BY rank DESC
"""


FALLBACK_FILTERED_BUNDLE_SQL = f"""
WITH kw AS (
    SELECT fc.id, fc.file_id, fc.start_byte, fc.end_byte, fc.title, fc.section, fc.snippet,
        f.title AS file_title,
        f.filename,
        {SOURCE_TITLE_SQL} AS source_title,
        ts_rank_cd(({SEARCH_VECTOR_SQL}), to_tsquery('english', :fallback_query)) AS rank
    FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    JOIN folders fo ON fo.id = f.folder_id
    JOIN bundle_files bf ON bf.file_id = f.id
    JOIN bundles b ON b.id = bf.bundle_id
    WHERE ({SEARCH_VECTOR_SQL}) @@ to_tsquery('english', :fallback_query)
        AND f.ruleset_id = :ruleset_id
        AND b.id = :bundle_id
        AND b.ruleset_id = :ruleset_id
        AND (
            (:user_id IS NULL AND b.is_public = TRUE AND f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
            OR (
                :user_id IS NOT NULL AND (
                    b.owner_id = :user_id
                    OR b.is_public = TRUE
                )
                AND (
                    (f.is_public = TRUE AND COALESCE(f.is_copyright_restricted, FALSE) = FALSE)
                    OR fo.user_id = :user_id
                    OR (
                        COALESCE(f.is_copyright_restricted, FALSE) = FALSE
                        AND EXISTS (
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
        )
    ORDER BY rank DESC
    LIMIT :k
)
SELECT id, file_id, start_byte, end_byte, title, section, snippet, file_title, filename, source_title, rank
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


QUESTION_PREFIX_PATTERNS = (
    re.compile(r"^(what|which)\s+(is|are)\s+", re.IGNORECASE),
    re.compile(r"^(what|which|how|when|why)\s+(does|do|did|can|should|would|will)\s+", re.IGNORECASE),
    re.compile(r"^(can|could|do|does|did|is|are|should|would|will)\s+", re.IGNORECASE),
    re.compile(r"^(tell me about|explain|describe|summarize)\s+", re.IGNORECASE),
)


TRAILING_FOCUS_WORDS = {
    "ability",
    "abilities",
    "effect",
    "effects",
    "mean",
    "means",
    "rule",
    "rules",
    "work",
    "works",
}


OPERATIVE_QUOTE_PATTERN = re.compile(
    r"\b(each time|if|when|while|unless|until|can|cannot|can't|must|may|add|subtract|improve|worsen|"
    r"eligible|target|move|shoot|fight|charge|attack|save|within|wholly|instead|only|never|always|"
    r"excluding|against|gain|lose|have|has)\b",
    re.IGNORECASE,
)


QUOTE_LEAD_PATTERNS = (
    re.compile(r"^(each time|if|when|while|unless|until)\b", re.IGNORECASE),
    re.compile(r"^(models?|units?)\s+(can|cannot|can't|must|may|have|has|gain|gains|lose|loses)\b", re.IGNORECASE),
    re.compile(r"^(add|subtract|improve|worsen)\b", re.IGNORECASE),
    re.compile(r"^(benefit of|sustained hits|lethal hits|devastating wounds|fights first)\b", re.IGNORECASE),
)


FLAVOR_HINTS = {
    "battlefield",
    "battlefields",
    "bombardment",
    "enemy salvoes",
    "enemy bombardment",
    "proud cities",
    "twisted wreckage",
    "shelter from enemy",
    "warriors",
    "scarred",
    "scars of war",
}


EXCEPTION_QUOTE_PATTERN = re.compile(
    r"\b(cannot|can't|does not|do not|except|unless|excluding|not cumulative|only|instead|"
    r"cannot have|cannot gain|does not apply|do not apply|not apply)\b",
    re.IGNORECASE,
)


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


def _normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_focus_phrase(query: str) -> str | None:
    quoted = re.findall(r'"([^"]+)"', query)
    if quoted:
        focus = _normalize_space(quoted[0].lower())
        return focus or None

    normalized = query.strip().lower()
    normalized = re.sub(r"[?!.]+$", "", normalized)
    for pattern in QUESTION_PREFIX_PATTERNS:
        normalized = pattern.sub("", normalized)
    normalized = re.sub(r"^(the|a|an)\s+", "", normalized).strip()
    tokens = [token for token in re.findall(r"[a-z0-9][a-z0-9+/-]*", normalized) if token]
    while tokens and tokens[-1] in TRAILING_FOCUS_WORDS:
        tokens.pop()
    filtered = [token for token in tokens if token not in QUESTION_STOPWORDS or token.isdigit()]
    if not filtered:
        return None
    return " ".join(tokens[:8]).strip() or None


def _query_terms(query: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9+/\-\s]+", " ", query.lower())
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
    return terms[:10]


def _best_anchor(text: str, focus_phrase: str | None, query_terms: list[str]) -> int:
    haystack = text.lower()
    if focus_phrase:
        anchor = haystack.find(focus_phrase)
        if anchor != -1:
            return anchor
    for term in sorted(query_terms, key=len, reverse=True):
        anchor = haystack.find(term)
        if anchor != -1:
            return anchor
    return -1


def _slice_excerpt(text: str, anchor: int, max_chars: int) -> str:
    if len(text) <= max_chars or anchor < 0:
        excerpt = text[:max_chars].strip()
        return excerpt

    start = max(0, anchor - max_chars // 3)
    end = min(len(text), start + max_chars)

    if start > 0:
        space_index = text.rfind(" ", 0, start)
        if space_index != -1 and start - space_index < 80:
            start = space_index + 1
    if end < len(text):
        space_index = text.find(" ", end)
        if space_index != -1 and space_index - end < 80:
            end = space_index

    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "... " + excerpt
    if end < len(text):
        excerpt = excerpt + " ..."
    return excerpt


def _build_excerpt(snippet: str, focus_phrase: str | None, query_terms: list[str], *, max_chars: int = 760) -> str:
    normalized = _normalize_space(snippet)
    anchor = _best_anchor(normalized, focus_phrase, query_terms)
    return _slice_excerpt(normalized, anchor, max_chars)


def _looks_like_heading_only(value: str) -> bool:
    words = re.findall(r"[A-Za-z0-9+/-]+", value)
    if not words:
        return True
    if len(words) > 8:
        return False
    alpha_chars = [char for char in value if char.isalpha()]
    if not alpha_chars:
        return True
    uppercase_ratio = sum(char.isupper() for char in alpha_chars) / len(alpha_chars)
    return uppercase_ratio > 0.85 and not OPERATIVE_QUOTE_PATTERN.search(value)


def _candidate_quote_fragments(snippet: str) -> list[str]:
    candidates: list[str] = []

    raw_lines = [_normalize_space(line.lstrip("•■- ").strip()) for line in snippet.splitlines()]
    lines = [line for line in raw_lines if line]
    for index, line in enumerate(lines):
        if len(line) >= 18:
            candidates.append(line)
        if index + 1 < len(lines) and (
            line.endswith(":")
            or _looks_like_heading_only(line)
            or len(line.split()) <= 4
        ):
            combined = _normalize_space(f"{line} {lines[index + 1]}")
            if len(combined) >= 18:
                candidates.append(combined)
        if index + 1 < len(lines) and not re.search(r"[.!?]$", line):
            combined = line
            for next_index in range(index + 1, min(index + 4, len(lines))):
                if _looks_like_heading_only(lines[next_index]):
                    break
                combined = _normalize_space(f"{combined} {lines[next_index]}")
                if len(combined) >= 18:
                    candidates.append(combined)
                if re.search(r"[.!?]$", combined):
                    break

    sentence_source = _normalize_space(snippet.replace("•", ". ").replace("■", ". "))
    sentences = [
        fragment.strip(" \"'")
        for fragment in re.split(r"(?<=[.!?])\s+", sentence_source)
        if fragment.strip(" \"'")
    ]
    for index, sentence in enumerate(sentences):
        candidates.append(sentence)
        if index + 1 < len(sentences) and len(sentence) + len(sentences[index + 1]) <= 280:
            candidates.append(_normalize_space(f"{sentence} {sentences[index + 1]}"))

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_space(candidate).strip(" \"'")
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(normalized)
    return unique_candidates


def _score_quote_candidate(candidate: str, focus_phrase: str | None, query_terms: list[str]) -> float:
    normalized = _normalize_space(candidate).strip(" \"'")
    if not normalized or len(normalized) < 18:
        return -100.0
    if _looks_like_heading_only(normalized):
        return -80.0

    lowered = normalized.lower()
    matched_terms = sum(1 for term in query_terms if term in lowered)
    coverage = matched_terms / max(len(query_terms), 1)
    exact_focus = 1.0 if focus_phrase and focus_phrase in lowered else 0.0

    score = coverage * 40.0 + exact_focus * 32.0
    if OPERATIVE_QUOTE_PATTERN.search(normalized):
        score += 18.0
    if any(pattern.search(normalized) for pattern in QUOTE_LEAD_PATTERNS):
        score += 10.0
    if ":" in normalized and matched_terms:
        score += 6.0
    if re.search(r"[.!?]$", normalized):
        score += 4.0
    elif len(normalized) < 120:
        score -= 10.0

    if 40 <= len(normalized) <= 220:
        score += 12.0
    elif len(normalized) <= 280:
        score += 4.0
    else:
        score -= 8.0

    flavor_hits = sum(1 for hint in FLAVOR_HINTS if hint in lowered)
    if flavor_hits and not OPERATIVE_QUOTE_PATTERN.search(normalized):
        score -= flavor_hits * 10.0
    elif flavor_hits:
        score -= flavor_hits * 3.0

    return score


def _extract_best_quotes(snippet: str, focus_phrase: str | None, query_terms: list[str], *, limit: int = 2) -> list[tuple[str, float]]:
    ranked = sorted(
        (
            (candidate, _score_quote_candidate(candidate, focus_phrase, query_terms))
            for candidate in _candidate_quote_fragments(snippet)
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    results: list[tuple[str, float]] = []
    if not ranked:
        return results

    for candidate, score in ranked:
        if score < 18:
            continue
        results.append((candidate, score))
        break

    if len(results) < limit:
        remaining = sorted(
            (
                (
                    candidate,
                    score + (12.0 if EXCEPTION_QUOTE_PATTERN.search(candidate) else 0.0),
                    score,
                )
                for candidate, score in ranked
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        for candidate, _, raw_score in remaining:
            if raw_score < 18:
                continue
            normalized = candidate.lower()
            if any(normalized in existing.lower() or existing.lower() in normalized for existing, _ in results):
                continue
            results.append((candidate, raw_score))
            if len(results) >= limit:
                break
    return results


def _score_chunk_match(row: dict, focus_phrase: str | None, query_terms: list[str]) -> float:
    header = _normalize_space(" ".join(filter(None, [row.get("title"), row.get("section"), row.get("source_title"), row.get("file_title")])))
    haystack = _normalize_space(" ".join(filter(None, [header, row.get("snippet")])))
    if not haystack:
        return 0.0

    lowered_haystack = haystack.lower()
    matched_terms = sum(1 for term in query_terms if term in lowered_haystack)
    coverage = matched_terms / max(len(query_terms), 1)
    exact_focus = 1.0 if focus_phrase and focus_phrase in lowered_haystack else 0.0
    header_focus = 1.0 if focus_phrase and focus_phrase in header.lower() else 0.0
    lexical_rank = min(float(row.get("rank") or 0.0), 1.0)
    return min(1.0, coverage * 0.45 + exact_focus * 0.35 + header_focus * 0.1 + lexical_rank * 0.2)


def _dedupe_and_focus_rows(rows: list[dict], query: str, *, k: int) -> list[dict]:
    focus_phrase = _extract_focus_phrase(query)
    query_terms = _query_terms(query)
    scored_rows: list[dict] = []
    seen_snippets: set[tuple[int, str]] = set()

    for raw_row in rows:
        row = dict(raw_row)
        row["source_title"] = row.get("source_title") or row.get("title") or row.get("section") or row.get("file_title") or row.get("filename")
        quote_candidates = _extract_best_quotes(row.get("snippet") or "", focus_phrase, query_terms)
        row["key_quote"] = quote_candidates[0][0] if quote_candidates else None
        row["supporting_quote"] = quote_candidates[1][0] if len(quote_candidates) > 1 else None
        if row["key_quote"]:
            normalized_snippet = _normalize_space(row.get("snippet") or "")
            quote_anchor = normalized_snippet.lower().find(row["key_quote"].lower())
            row["excerpt"] = _slice_excerpt(normalized_snippet, quote_anchor, 520)
        else:
            row["excerpt"] = _build_excerpt(row.get("snippet") or "", focus_phrase, query_terms, max_chars=520)
        quote_strength = min(1.0, max(0.0, quote_candidates[0][1] / 100.0)) if quote_candidates else 0.0
        row["match_score"] = min(1.0, _score_chunk_match(row, focus_phrase, query_terms) + quote_strength * 0.12)
        dedupe_key = (int(row.get("file_id") or 0), row["excerpt"][:240].lower())
        if dedupe_key in seen_snippets:
            continue
        seen_snippets.add(dedupe_key)
        scored_rows.append(row)

    scored_rows.sort(
        key=lambda row: (
            float(row.get("match_score") or 0.0),
            float(row.get("rank") or 0.0),
        ),
        reverse=True,
    )

    results: list[dict] = []
    per_file_counts: dict[int, int] = {}
    for row in scored_rows:
        file_id = int(row.get("file_id") or 0)
        if per_file_counts.get(file_id, 0) >= 3 and len(scored_rows) > k:
            continue
        per_file_counts[file_id] = per_file_counts.get(file_id, 0) + 1
        results.append(row)
        if len(results) >= k:
            break
    return results


def estimate_retrieval_quality(chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    top_chunks = chunks[: min(3, len(chunks))]
    return min(
        1.0,
        sum(float(chunk.get("match_score") or 0.0) for chunk in top_chunks) / len(top_chunks),
    )


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
            return _dedupe_and_focus_rows([dict(r) for r in rows], normalized_query, k=k)

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
        return _dedupe_and_focus_rows([dict(r) for r in rows], normalized_query, k=k)
