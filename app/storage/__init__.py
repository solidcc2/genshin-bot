from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.config import StorageConfig


class StorageProvider(ABC):
    @abstractmethod
    async def get(self, namespace: str, key: str) -> Any | None:
        ...

    @abstractmethod
    async def set(
        self, namespace: str, key: str, value: Any, ttl: float | None = None
    ) -> None:
        ...

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        ...

    @abstractmethod
    async def list(self, namespace: str) -> list[str]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


def create_storage(config: StorageConfig) -> StorageProvider:
    if config.backend == "memory":
        from app.storage.memory import MemoryStorage

        return MemoryStorage()
    elif config.backend == "sqlite":
        from app.storage.sqlite import SQLiteStorage

        return SQLiteStorage(config.db_path)
    else:
        raise ValueError(f"Unknown storage backend: {config.backend}")
