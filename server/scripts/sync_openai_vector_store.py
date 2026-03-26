from __future__ import annotations

import argparse
import asyncio
import mimetypes
from pathlib import Path

from app.config import settings
from app.services.openai_vector_store import sync_file_to_vector_store


DEFAULT_DIRS = ("rules", "templates", "examples", "uploads")


def iter_source_files(knowledge_root: Path, include_dirs: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for dirname in include_dirs:
        base = knowledge_root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                files.append(path)
    return files


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local knowledge files into the configured OpenAI vector store.")
    parser.add_argument(
        "--knowledge-root",
        default=str(Path(__file__).resolve().parents[2] / "knowledge"),
        help="Path to the local knowledge workspace.",
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=list(DEFAULT_DIRS),
        help="Knowledge subdirectories to sync.",
    )
    args = parser.parse_args()

    if not settings.OPENAI_VECTOR_STORE_ID:
        raise SystemExit("OPENAI_VECTOR_STORE_ID is required")
    if not settings.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is required")

    knowledge_root = Path(args.knowledge_root).resolve()
    files = iter_source_files(knowledge_root, tuple(args.dirs))
    if not files:
        print("No files found to sync.")
        return

    print(f"Syncing {len(files)} file(s) to vector store {settings.OPENAI_VECTOR_STORE_ID}...")
    for path in files:
        rel_path = path.relative_to(knowledge_root)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        result = await sync_file_to_vector_store(
            filename=path.name,
            mime_type=mime_type,
            data=path.read_bytes(),
            vector_store_id=settings.OPENAI_VECTOR_STORE_ID,
            attributes={
                "source": "knowledge_sync",
                "relative_path": rel_path.as_posix(),
                "category": rel_path.parts[0],
            },
        )
        print(
            f"- {rel_path.as_posix()} -> file={result['openai_file_id']} "
            f"vector_store_file={result['openai_vector_store_file_id']} "
            f"status={result['openai_vector_store_status']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
