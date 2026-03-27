from __future__ import annotations

import hashlib
import os
from pathlib import Path


def _clean_env_value(value: str | None) -> str:
    if not value:
        return ""
    return value.split("#", 1)[0].strip()


def _env_int(name: str, default: int) -> int:
    raw = _clean_env_value(os.getenv(name))
    if not raw:
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    return bool(_env_int(name, int(default)))


def _default_jwt_secret() -> str:
    project_root = Path(__file__).resolve().parents[1]
    seed = f"lexmechanicus-dev:{project_root}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _resolve_jwt_secret() -> str:
    configured = _clean_env_value(os.getenv("JWT_SECRET"))
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
    OPENAI_VECTOR_STORE_AUTO_SYNC = _env_bool("OPENAI_VECTOR_STORE_AUTO_SYNC", True)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT")
    FEATURE_AUTO_ESCALATE = _env_bool("FEATURE_AUTO_ESCALATE", True)
    RATE_LIMIT_PER_MIN = _env_int("RATE_LIMIT_PER_MIN", 30)
    RATE_LIMIT_PER_DAY = _env_int("RATE_LIMIT_PER_DAY", 1000)
    JWT_SECRET = _resolve_jwt_secret()
    ACCESS_TOKEN_TTL_HOURS = _env_int("ACCESS_TOKEN_TTL_HOURS", 72)
    GUEST_ID_HEADER = os.getenv("GUEST_ID_HEADER", "X-Guest-Id")
    FREE_TOKENS_PER_HOUR = _env_int("FREE_TOKENS_PER_HOUR", 1200)
    FREE_RESPONSE_TOKEN_RESERVE = _env_int("FREE_RESPONSE_TOKEN_RESERVE", 240)


settings = Settings()
