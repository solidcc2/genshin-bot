from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.errors import StorageError
from app.storage import StorageProvider


class SQLiteStorage(StorageProvider):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def _init(self) -> aiosqlite.Connection:
        if self._conn is not None:
            return self._conn

        parent = Path(self._db_path).parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute(
            """CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                expires_at REAL,
                PRIMARY KEY (namespace, key)
            )"""
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kv_namespace ON kv_store(namespace)"
        )
        await self._conn.commit()
        return self._conn

    async def get(self, namespace: str, key: str) -> Any | None:
        conn = await self._init()
        async with conn.execute(
            "SELECT value, expires_at FROM kv_store WHERE namespace = ? AND key = ?",
            (namespace, key),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        expires_at = row["expires_at"]
        if expires_at is not None and datetime.now(timezone.utc).timestamp() > expires_at:
            await self.delete(namespace, key)
            return None

        return json.loads(row["value"])

    async def set(
        self, namespace: str, key: str, value: Any, ttl: float | None = None
    ) -> None:
        conn = await self._init()
        expires_at: float | None = None
        if ttl is not None:
            expires_at = datetime.now(timezone.utc).timestamp() + ttl

        serialized = json.dumps(value, ensure_ascii=False)
        try:
            await conn.execute(
                """INSERT OR REPLACE INTO kv_store (namespace, key, value, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (namespace, key, serialized, expires_at),
            )
            await conn.commit()
        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to set {namespace}:{key}: {exc}") from exc

    async def delete(self, namespace: str, key: str) -> bool:
        conn = await self._init()
        cursor = await conn.execute(
            "DELETE FROM kv_store WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def list(self, namespace: str) -> list[str]:
        conn = await self._init()
        now = datetime.now(timezone.utc).timestamp()
        async with conn.execute(
            "SELECT key, expires_at FROM kv_store WHERE namespace = ?",
            (namespace,),
        ) as cursor:
            rows = await cursor.fetchall()

        keys: list[str] = []
        for row in rows:
            expires_at = row["expires_at"]
            if expires_at is not None and now > expires_at:
                await conn.execute(
                    "DELETE FROM kv_store WHERE namespace = ? AND key = ?",
                    (namespace, row["key"]),
                )
            else:
                keys.append(row["key"])
        if len(keys) < len(rows):
            await conn.commit()
        return sorted(keys)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
