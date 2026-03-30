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


def _env_csv(name: str) -> list[str]:
    raw = _clean_env_value(os.getenv(name))
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_jwt_secret() -> str:
    project_root = Path(__file__).resolve().parents[1]
    seed = f"cogitator-dev:{project_root}"
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
    OPENAI_AGENT_NAME = os.getenv("OPENAI_AGENT_NAME", "Cogitator Rules Agent")
    OPENAI_VECTOR_STORE_AUTO_SYNC = _env_bool("OPENAI_VECTOR_STORE_AUTO_SYNC", False)
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
    SMTP_HOST = _clean_env_value(os.getenv("SMTP_HOST"))
    SMTP_PORT = _env_int("SMTP_PORT", 587)
    SMTP_USERNAME = _clean_env_value(os.getenv("SMTP_USERNAME"))
    SMTP_PASSWORD = _clean_env_value(os.getenv("SMTP_PASSWORD"))
    SMTP_FROM_EMAIL = _clean_env_value(os.getenv("SMTP_FROM_EMAIL"))
    SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", True)
    SMTP_USE_SSL = _env_bool("SMTP_USE_SSL", False)
    ADMIN_TAKEDOWN_EMAILS = _env_csv("ADMIN_TAKEDOWN_EMAILS")
    ADMIN_REVIEW_TOKEN = _clean_env_value(os.getenv("ADMIN_REVIEW_TOKEN"))
    PUBLIC_APP_URL = _clean_env_value(os.getenv("PUBLIC_APP_URL"))
    SERVICE_PROVIDER_LEGAL_NAME = _clean_env_value(os.getenv("SERVICE_PROVIDER_LEGAL_NAME")) or "Cogitator"
    SERVICE_PROVIDER_ADDRESS = _clean_env_value(os.getenv("SERVICE_PROVIDER_ADDRESS"))
    SERVICE_PROVIDER_ALT_NAMES = _env_csv("SERVICE_PROVIDER_ALT_NAMES")
    DMCA_DESIGNATED_AGENT_NAME = _clean_env_value(os.getenv("DMCA_DESIGNATED_AGENT_NAME"))
    DMCA_DESIGNATED_AGENT_ORGANIZATION = _clean_env_value(os.getenv("DMCA_DESIGNATED_AGENT_ORGANIZATION"))
    DMCA_DESIGNATED_AGENT_EMAIL = _clean_env_value(os.getenv("DMCA_DESIGNATED_AGENT_EMAIL"))
    DMCA_DESIGNATED_AGENT_PHONE = _clean_env_value(os.getenv("DMCA_DESIGNATED_AGENT_PHONE"))
    DMCA_DESIGNATED_AGENT_ADDRESS = _clean_env_value(os.getenv("DMCA_DESIGNATED_AGENT_ADDRESS"))
    DMCA_REPEAT_INFRINGER_THRESHOLD = _env_int("DMCA_REPEAT_INFRINGER_THRESHOLD", 2)
    DMCA_COUNTER_RESTORE_AFTER_BUSINESS_DAYS = _env_int("DMCA_COUNTER_RESTORE_AFTER_BUSINESS_DAYS", 10)
    DMCA_COUNTER_RESTORE_DEADLINE_BUSINESS_DAYS = _env_int("DMCA_COUNTER_RESTORE_DEADLINE_BUSINESS_DAYS", 14)
    TERMS_VERSION = _clean_env_value(os.getenv("TERMS_VERSION")) or "2026-03-27"
    LEGAL_POLICY_LAST_UPDATED = _clean_env_value(os.getenv("LEGAL_POLICY_LAST_UPDATED")) or "2026-03-27"


settings = Settings()
