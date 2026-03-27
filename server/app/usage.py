from __future__ import annotations

import hashlib
import math
import redis.asyncio as aioredis
from fastapi import Request, status
from redis.exceptions import RedisError

from .config import settings
from .errors import raise_api_error


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def resolve_guest_key(request: Request) -> str:
    guest_id = (request.headers.get(settings.GUEST_ID_HEADER) or "").strip()
    client_host = request.client.host if request.client else "unknown"
    raw_key = guest_id or f"ip:{client_host}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class AnonymousUsageGate:
    def __init__(self):
        self._redis = None

    async def init(self):
        if not self._redis:
            try:
                self._redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except RedisError:
                raise_api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Usage tracking is temporarily unavailable.",
                    "USAGE_TRACKING_UNAVAILABLE",
                )
        return self._redis

    async def _get_key(self, guest_key: str) -> str:
        await self.init()
        return f"guest_tokens:{guest_key}"

    async def get_status(self, guest_key: str):
        redis = self._redis or await self.init()
        key = await self._get_key(guest_key)
        try:
            raw_used = await redis.get(key)
            ttl = await redis.ttl(key)
        except RedisError:
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Usage tracking is temporarily unavailable.",
                "USAGE_TRACKING_UNAVAILABLE",
            )
        used = int(raw_used or 0)
        remaining = max(0, settings.FREE_TOKENS_PER_HOUR - used)
        reset_in_seconds = ttl if ttl and ttl > 0 else 3600
        return {
            "limit": settings.FREE_TOKENS_PER_HOUR,
            "used": used,
            "remaining": remaining,
            "reset_in_seconds": reset_in_seconds,
            "exhausted": remaining <= 0,
        }

    async def reserve(self, guest_key: str, prompt: str):
        redis = self._redis or await self.init()
        key = await self._get_key(guest_key)
        input_tokens = estimate_tokens(prompt)
        reserved_total = input_tokens + settings.FREE_RESPONSE_TOKEN_RESERVE
        try:
            used = await redis.incrby(key, reserved_total)
            ttl = await redis.ttl(key)
        except RedisError:
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Usage tracking is temporarily unavailable.",
                "USAGE_TRACKING_UNAVAILABLE",
            )
        if ttl is None or ttl < 0:
            try:
                await redis.expire(key, 3600)
            except RedisError:
                raise_api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Usage tracking is temporarily unavailable.",
                    "USAGE_TRACKING_UNAVAILABLE",
                )
            ttl = 3600

        if used > settings.FREE_TOKENS_PER_HOUR:
            try:
                await redis.decrby(key, reserved_total)
            except RedisError:
                raise_api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Usage tracking is temporarily unavailable.",
                    "USAGE_TRACKING_UNAVAILABLE",
                )
            remaining = max(0, settings.FREE_TOKENS_PER_HOUR - (used - reserved_total))
            raise_api_error(
                status.HTTP_401_UNAUTHORIZED,
                "You have used all free tokens for this hour. Create an account to keep chatting now.",
                "ACCOUNT_REQUIRED",
                free_usage={
                    "limit": settings.FREE_TOKENS_PER_HOUR,
                    "used": settings.FREE_TOKENS_PER_HOUR - remaining,
                    "remaining": remaining,
                    "reset_in_seconds": ttl,
                    "exhausted": True,
                },
            )

        return {
            "input_tokens": input_tokens,
            "reserved_total": reserved_total,
        }

    async def finalize(self, guest_key: str, reservation: dict | None, output_text: str):
        if not reservation:
            return
        redis = self._redis or await self.init()
        key = await self._get_key(guest_key)
        actual_total = reservation["input_tokens"] + estimate_tokens(output_text)
        delta = actual_total - reservation["reserved_total"]
        if delta:
            try:
                await redis.incrby(key, delta)
            except RedisError:
                raise_api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Usage tracking is temporarily unavailable.",
                    "USAGE_TRACKING_UNAVAILABLE",
                )
        try:
            ttl = await redis.ttl(key)
        except RedisError:
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Usage tracking is temporarily unavailable.",
                "USAGE_TRACKING_UNAVAILABLE",
            )
        if ttl is None or ttl < 0:
            try:
                await redis.expire(key, 3600)
            except RedisError:
                raise_api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Usage tracking is temporarily unavailable.",
                    "USAGE_TRACKING_UNAVAILABLE",
                )
