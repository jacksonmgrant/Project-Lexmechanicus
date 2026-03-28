from __future__ import annotations

from io import BytesIO
import re

from markdown_it import MarkdownIt
from pypdf import PdfReader


md = MarkdownIt()

TITLE_MAX_LENGTH = 120
MAX_TITLE_SCAN_LINES = 24
TITLE_BOILERPLATE_PATTERNS = (
    re.compile(r"^(page|p\.?)\s*\d+(\s*(of|/)\s*\d+)?$", re.IGNORECASE),
    re.compile(r"^\d+\s*(of|/)\s*\d+$", re.IGNORECASE),
    re.compile(r"^(table of contents|contents)$", re.IGNORECASE),
    re.compile(r"^(copyright|all rights reserved|published by)\b", re.IGNORECASE),
    re.compile(r"^(www\.|https?://)", re.IGNORECASE),
    re.compile(r".+@.+\..+"),
)
GENERIC_TITLE_VALUES = {
    "document",
    "untitled",
    "title",
    "scan",
    "image",
    "file",
}
GENERIC_SECTION_HEADINGS = {
    "introduction",
    "overview",
    "contents",
    "appendix",
    "credits",
    "reference",
}
CORPORATE_WORDS = {
    "inc",
    "inc.",
    "llc",
    "ltd",
    "ltd.",
    "limited",
    "corp",
    "corp.",
    "company",
    "games workshop",
}


def _clean_title(value: str | None, max_length: int = TITLE_MAX_LENGTH) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).replace("\x00", " ").replace("\ufeff", " ").split())
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+([:;,.!?])", r"\1", cleaned)
    return cleaned[:max_length]


def build_default_file_title(filename: str) -> str:
    stripped = re.sub(r"\.[^.]+$", "", filename or "")
    normalized = re.sub(r"[_-]+", " ", stripped)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or (filename or "")


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore").replace("\ufeff", "")


def _normalize_metadata_title(value: str | None) -> str | None:
    cleaned = _clean_title(value)
    if not cleaned:
        return None
    cleaned = re.sub(r"^(microsoft\s+(word|powerpoint|excel)\s*-\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\.(pdf|docx?|pptx?|txt|md)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = _clean_title(cleaned)
    if not cleaned:
        return None
    if cleaned.strip().lower() in GENERIC_TITLE_VALUES:
        return None
    return cleaned


def _is_boilerplate_title_line(line: str) -> bool:
    normalized = line.strip()
    lowered = normalized.lower()
    if not normalized:
        return True
    if not re.search(r"[A-Za-z]", normalized):
        return True
    if len(normalized) < 4 or len(normalized) > TITLE_MAX_LENGTH:
        return True
    if normalized.endswith("."):
        return True
    if sum(char.isdigit() for char in normalized) > max(6, len(normalized) // 3):
        return True
    if any(pattern.match(normalized) for pattern in TITLE_BOILERPLATE_PATTERNS):
        return True
    if any(symbol in normalized for symbol in ("@", "http://", "https://", "www.")):
        return True
    if any(token in lowered for token in ("copyright", "all rights reserved", "table of contents")):
        return True
    return False


def _word_tokens(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'&:+/-]*", value)


def _titleish_ratio(value: str) -> float:
    words = _word_tokens(value)
    if not words:
        return 0.0
    titleish_words = 0
    for word in words:
        if any(char.isdigit() for char in word):
            titleish_words += 1
            continue
        if word.isupper() or word[0].isupper():
            titleish_words += 1
    return titleish_words / len(words)


def _looks_like_sentence(value: str) -> bool:
    words = _word_tokens(value)
    if len(words) >= 14:
        return True
    lowercase_words = sum(1 for word in words if word[:1].islower())
    return bool(words) and lowercase_words / len(words) > 0.55 and value.endswith((".", "!", "?"))


def _score_title_candidate(value: str, *, position: int, window_size: int, default_title: str) -> int:
    cleaned = _clean_title(value)
    if not cleaned or _is_boilerplate_title_line(cleaned):
        return -100

    lowered = cleaned.lower()
    words = _word_tokens(cleaned)
    score = 0

    score += max(0, 18 - (position * 2))

    if 2 <= len(words) <= 10:
        score += 18
    elif len(words) == 1:
        score += 6
    elif len(words) <= 14:
        score += 8
    else:
        score -= 15

    if 8 <= len(cleaned) <= 80:
        score += 14
    elif len(cleaned) <= 100:
        score += 4
    else:
        score -= 20

    score += int(_titleish_ratio(cleaned) * 20)
    score += min(10, (window_size - 1) * 5)

    if ":" in cleaned or " - " in cleaned:
        score += 4
    if cleaned.isupper() and len(words) <= 6:
        score += 6
    if lowered == default_title.strip().lower():
        score -= 35
    if _looks_like_sentence(cleaned):
        score -= 20
    if any(lowered.endswith(suffix) for suffix in CORPORATE_WORDS):
        score -= 18
    if lowered in {"introduction", "overview", "appendix", "credits"}:
        score -= 15

    return score


def _join_title_lines(lines: list[str]) -> str:
    return _clean_title(" ".join(line.strip() for line in lines if line.strip())) or ""


def _pick_title_from_lines(lines: list[str], *, default_title: str = "") -> str | None:
    cleaned_lines = [_clean_title(line) for line in lines[:MAX_TITLE_SCAN_LINES]]
    normalized_lines = [line for line in cleaned_lines if line]
    if not normalized_lines:
        return None

    best_title: str | None = None
    best_score = 0

    for index, line in enumerate(normalized_lines):
        if _is_boilerplate_title_line(line):
            continue

        for window_size in (1, 2, 3):
            window = normalized_lines[index:index + window_size]
            if len(window) != window_size:
                continue
            if any(_is_boilerplate_title_line(part) for part in window):
                continue
            if any(_looks_like_sentence(part) for part in window):
                continue
            if any(part.lower() in GENERIC_SECTION_HEADINGS for part in window):
                continue

            candidate = _join_title_lines(window)
            score = _score_title_candidate(
                candidate,
                position=index,
                window_size=window_size,
                default_title=default_title,
            )
            if score > best_score:
                best_title = candidate
                best_score = score

    return best_title if best_score >= 20 else None


def _extract_title_from_pdf(data: bytes, *, filename: str = "") -> str | None:
    reader = PdfReader(BytesIO(data))
    metadata = reader.metadata or {}
    default_title = build_default_file_title(filename)
    metadata_title = _normalize_metadata_title(getattr(metadata, "title", None) or metadata.get("/Title"))
    if metadata_title and _score_title_candidate(metadata_title, position=0, window_size=1, default_title=default_title) >= 18:
        return metadata_title

    candidate_lines: list[str] = []
    for page in reader.pages[:2]:
        text = page.extract_text() or ""
        for line in text.splitlines():
            cleaned = _clean_title(line)
            if cleaned:
                candidate_lines.append(cleaned)
            if len(candidate_lines) >= MAX_TITLE_SCAN_LINES:
                break
        if len(candidate_lines) >= MAX_TITLE_SCAN_LINES:
            break

    return _pick_title_from_lines(candidate_lines, default_title=default_title)


def _strip_markdown_frontmatter(text: str) -> str:
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return text
    lines = stripped.splitlines()
    for index in range(1, min(len(lines), 20)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1:])
    return text


def _extract_title_from_markdown(data: bytes, *, filename: str = "") -> str | None:
    text = _strip_markdown_frontmatter(_decode_text(data))
    lines = text.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = _clean_title(stripped.lstrip("#").strip())
            if heading and not _is_boilerplate_title_line(heading):
                return heading
        if index + 1 < len(lines) and re.fullmatch(r"[=-]{3,}", lines[index + 1].strip()):
            heading = _clean_title(stripped)
            if heading and not _is_boilerplate_title_line(heading):
                return heading

    return _pick_title_from_lines(lines, default_title=build_default_file_title(filename))


def _extract_title_from_text(data: bytes, *, filename: str = "") -> str | None:
    return _pick_title_from_lines(_decode_text(data).splitlines(), default_title=build_default_file_title(filename))


def extract_document_title(mime: str, data: bytes, filename: str = "") -> str | None:
    default_title = _clean_title(build_default_file_title(filename))
    try:
        if mime == "application/pdf":
            return _extract_title_from_pdf(data, filename=filename) or default_title
        if mime in ("text/markdown", "text/x-markdown"):
            return _extract_title_from_markdown(data, filename=filename) or default_title
        if mime == "text/plain":
            return _extract_title_from_text(data, filename=filename) or default_title
    except Exception:
        return default_title
    return default_title


def should_replace_with_extracted_title(title: str, filename: str) -> bool:
    normalized_title = title.strip().lower()
    if not normalized_title:
        return True
    return normalized_title == build_default_file_title(filename).strip().lower()


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_text_from_markdown(data: bytes) -> str:
    # Convert markdown to plain text by stripping tokens.
    tokens = md.parse(data.decode("utf-8", errors="ignore"))
    out: list[str] = []
    for t in tokens:
        if t.type == "inline" and t.content:
            out.append(t.content)
    return "\n".join(out)


def normalize_text(mime: str, data: bytes) -> str:
    if mime in ("application/pdf",):
        return extract_text_from_pdf(data)
    if mime in ("text/markdown", "text/x-markdown", "text/plain"):
        return extract_text_from_markdown(data) if mime != "text/plain" else data.decode("utf-8", errors="ignore")
    # Unknown types: best-effort raw decode.
    return data.decode("utf-8", errors="ignore")
