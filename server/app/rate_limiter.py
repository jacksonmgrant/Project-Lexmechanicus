from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import HTTPException

from .config import settings


class RateLimiter:
    def __init__(self):
        self._redis = None

    async def init(self):
        if not self._redis:
            self._redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
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
        m, _, d, _ = await pipe.execute()

        if m > per_min:
            raise HTTPException(429, detail="Rate limit per minute exceeded")
        if d > per_day:
            raise HTTPException(429, detail="Daily rate limit exceeded")
