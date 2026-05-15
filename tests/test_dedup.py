from __future__ import annotations

import pytest

from app.dedup import MessageDedupStore
from app.storage.memory import MemoryStorage


@pytest.fixture
def dedup():
    storage = MemoryStorage()
    return MessageDedupStore(storage)


class TestMessageDedupStore:
    @pytest.mark.anyio
    async def test_not_duplicate_initially(self, dedup) -> None:
        assert await dedup.is_duplicate("msg_001") is False

    @pytest.mark.anyio
    async def test_detects_duplicate_after_mark(self, dedup) -> None:
        await dedup.mark_seen("msg_001")
        assert await dedup.is_duplicate("msg_001") is True

    @pytest.mark.anyio
    async def test_does_not_affect_other_ids(self, dedup) -> None:
        await dedup.mark_seen("msg_001")
        assert await dedup.is_duplicate("msg_002") is False

    @pytest.mark.anyio
    async def test_ttl_expiry(self, dedup) -> None:
        await dedup.mark_seen("msg_001")
        # set ttl to 0 so expires instantly — use a fresh store with ttl=0
        storage = MemoryStorage()
        dedup2 = MessageDedupStore(storage, ttl=0.0)
        await dedup2.mark_seen("msg_002")
        assert await dedup2.is_duplicate("msg_002") is False

    @pytest.mark.anyio
    async def test_multiple_ids_independent(self, dedup) -> None:
        await dedup.mark_seen("a")
        await dedup.mark_seen("b")
        assert await dedup.is_duplicate("a") is True
        assert await dedup.is_duplicate("b") is True
        assert await dedup.is_duplicate("c") is False

    @pytest.mark.anyio
    async def test_mark_seen_idempotent(self, dedup) -> None:
        await dedup.mark_seen("msg_001")
        await dedup.mark_seen("msg_001")  # should not raise
        assert await dedup.is_duplicate("msg_001") is True
