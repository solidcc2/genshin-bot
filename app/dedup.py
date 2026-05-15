from __future__ import annotations

from app.storage import StorageProvider


_NS_DEDUP = "dedup"


class MessageDedupStore:
    def __init__(self, storage: StorageProvider, ttl: float = 300.0) -> None:
        self._storage = storage
        self._ttl = ttl

    async def is_duplicate(self, message_id: str) -> bool:
        seen = await self._storage.get(_NS_DEDUP, message_id)
        return seen is not None

    async def mark_seen(self, message_id: str) -> None:
        await self._storage.set(_NS_DEDUP, message_id, True, ttl=self._ttl)
