# -*- coding: utf-8 -*-
from aioredis import Redis

from app.config import (
    CACHE_ENABLE,
    CACHE_REDIS_DB,
    CACHE_REDIS_HOST,
    CACHE_REDIS_PASSWORD,
    CACHE_REDIS_PORT,
)


class Cache:
    def __init__(self):
        if CACHE_ENABLE:
            self._redis: Redis = Redis(
                host=CACHE_REDIS_HOST,
                port=CACHE_REDIS_PORT,
                password=CACHE_REDIS_PASSWORD,
                db=CACHE_REDIS_DB,
            )
        else:
            self._redis = None

    async def get(self, key: str) -> str | None:
        if self._redis:
            return await self._redis.get(key)
        return None

    async def set(self, key: str, value: str, timeout: int = None) -> None:
        if self._redis:
            await self._redis.set(key, value, timeout)

    async def delete(self, key: str) -> None:
        if self._redis:
            await self._redis.delete(key)


cache = Cache()
