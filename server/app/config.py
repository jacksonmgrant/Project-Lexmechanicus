from __future__ import annotations

import hashlib
import os
from pathlib import Path


def _default_jwt_secret() -> str:
    project_root = Path(__file__).resolve().parents[1]
    seed = f"lexmechanicus-dev:{project_root}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _resolve_jwt_secret() -> str:
    configured = (os.getenv("JWT_SECRET") or "").strip()
    if configured and configured.lower() not in {"change-me", "changeme", "dev-secret"} and len(configured) >= 32:
        return configured
    return _default_jwt_secret()


class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
    OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
    GPT5_MINI_MODEL = os.getenv("GPT5_MINI_MODEL", "gpt-5-mini")
    GPT5_FULL_MODEL = os.getenv("GPT5_FULL_MODEL", "gpt-5")
    EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")
    OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")
    OPENAI_AGENT_NAME = os.getenv("OPENAI_AGENT_NAME", "Lexmechanicus Rules Agent")
    OPENAI_VECTOR_STORE_AUTO_SYNC = bool(int(os.getenv("OPENAI_VECTOR_STORE_AUTO_SYNC", "1")))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT")
    FEATURE_AUTO_ESCALATE = bool(int(os.getenv("FEATURE_AUTO_ESCALATE", "1")))
    RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
    RATE_LIMIT_PER_DAY = int(os.getenv("RATE_LIMIT_PER_DAY", "1000"))
    JWT_SECRET = _resolve_jwt_secret()
    ACCESS_TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "72"))
    GUEST_ID_HEADER = os.getenv("GUEST_ID_HEADER", "X-Guest-Id")
    FREE_TOKENS_PER_HOUR = int(os.getenv("FREE_TOKENS_PER_HOUR", "1200"))
    FREE_RESPONSE_TOKEN_RESERVE = int(os.getenv("FREE_RESPONSE_TOKEN_RESERVE", "240"))


settings = Settings()
