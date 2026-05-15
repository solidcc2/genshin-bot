from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.storage import StorageProvider


class MemoryStorage(StorageProvider):
    def __init__(self) -> None:
        self._data: dict[str, dict[str, tuple[Any, float | None]]] = {}
        # _data[namespace][key] = (serialized_value, expires_at_timestamp_or_None)

    async def get(self, namespace: str, key: str) -> Any | None:
        store = self._data.get(namespace)
        if store is None:
            return None

        entry = store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if expires_at is not None and datetime.now(timezone.utc).timestamp() > expires_at:
            del store[key]
            return None

        return json.loads(value)

    async def set(
        self, namespace: str, key: str, value: Any, ttl: float | None = None
    ) -> None:
        if namespace not in self._data:
            self._data[namespace] = {}

        expires_at: float | None = None
        if ttl is not None:
            expires_at = datetime.now(timezone.utc).timestamp() + ttl

        self._data[namespace][key] = (json.dumps(value, ensure_ascii=False), expires_at)

    async def delete(self, namespace: str, key: str) -> bool:
        store = self._data.get(namespace)
        if store is None:
            return False

        if key not in store:
            return False

        del store[key]
        return True

    async def list(self, namespace: str) -> list[str]:
        store = self._data.get(namespace)
        if store is None:
            return []

        now = datetime.now(timezone.utc).timestamp()
        keys: list[str] = []
        for key, (_, expires_at) in list(store.items()):
            if expires_at is not None and now > expires_at:
                del store[key]
            else:
                keys.append(key)
        return sorted(keys)

    async def close(self) -> None:
        self._data.clear()
