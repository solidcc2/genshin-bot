from __future__ import annotations

from datetime import datetime, timezone

from app.storage import StorageProvider


_NS_RATELIMIT = "ratelimit"


class RateLimiter:
    def __init__(self, storage: StorageProvider) -> None:
        self._storage = storage

    async def check(self, bucket: str, limit: int, window: float) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        timestamps = await self._storage.get(_NS_RATELIMIT, bucket) or []

        cutoff = now - window
        valid = [t for t in timestamps if t > cutoff]

        if len(valid) >= limit:
            return False

        valid.append(now)
        await self._storage.set(_NS_RATELIMIT, bucket, valid, ttl=window)
        return True
