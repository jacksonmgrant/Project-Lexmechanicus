from __future__ import annotations

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from .config import settings
from .errors import raise_api_error


class RateLimiter:
    def __init__(self):
        self._redis = None

    async def init(self):
        if not self._redis:
            try:
                self._redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except RedisError:
                raise_api_error(503, "Rate limiting is temporarily unavailable.", "RATE_LIMITER_UNAVAILABLE")
        return self._redis

    async def check(self, user_key: str):
        r = self._redis or await self.init()
        per_min = settings.RATE_LIMIT_PER_MIN
        per_day = settings.RATE_LIMIT_PER_DAY

        pipe = r.pipeline()
        pipe.incr(f"rl:{user_key}:m")
        pipe.expire(f"rl:{user_key}:m", 60)
        pipe.incr(f"rl:{user_key}:d")
        pipe.expire(f"rl:{user_key}:d", 86400)
        try:
            m, _, d, _ = await pipe.execute()
        except RedisError:
            raise_api_error(503, "Rate limiting is temporarily unavailable.", "RATE_LIMITER_UNAVAILABLE")

        if m > per_min:
            raise_api_error(429, "You have sent too many requests in the last minute.", "RATE_LIMIT_MINUTE_EXCEEDED")
        if d > per_day:
            raise_api_error(429, "You have reached the daily request limit.", "RATE_LIMIT_DAY_EXCEEDED")
