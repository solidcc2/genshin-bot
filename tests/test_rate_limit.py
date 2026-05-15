from __future__ import annotations

import pytest

from app.rate_limit import RateLimiter
from app.storage.memory import MemoryStorage


@pytest.fixture
def limiter():
    storage = MemoryStorage()
    return RateLimiter(storage)


class TestRateLimiter:
    @pytest.mark.anyio
    async def test_allows_within_limit(self, limiter) -> None:
        for _ in range(5):
            ok = await limiter.check("bucket:test", limit=5, window=60.0)
            assert ok is True

    @pytest.mark.anyio
    async def test_blocks_over_limit(self, limiter) -> None:
        for _ in range(5):
            await limiter.check("bucket:test", limit=5, window=60.0)

        ok = await limiter.check("bucket:test", limit=5, window=60.0)
        assert ok is False

    @pytest.mark.anyio
    async def test_allows_different_buckets_independently(self, limiter) -> None:
        for _ in range(5):
            await limiter.check("bucket:a", limit=5, window=60.0)

        ok = await limiter.check("bucket:b", limit=5, window=60.0)
        assert ok is True

    @pytest.mark.anyio
    async def test_window_slides(self, limiter) -> None:
        # fill the bucket
        for _ in range(3):
            await limiter.check("bucket:slide", limit=3, window=0.0)
        ok = await limiter.check("bucket:slide", limit=3, window=0.0)
        assert ok is True  # all previous timestamps expired

    @pytest.mark.anyio
    async def test_limit_one(self, limiter) -> None:
        ok1 = await limiter.check("bucket:once", limit=1, window=60.0)
        assert ok1 is True

        ok2 = await limiter.check("bucket:once", limit=1, window=60.0)
        assert ok2 is False

    @pytest.mark.anyio
    async def test_different_limits_per_bucket(self, limiter) -> None:
        assert await limiter.check("bucket:low", limit=2, window=60.0) is True
        assert await limiter.check("bucket:low", limit=2, window=60.0) is True
        assert await limiter.check("bucket:low", limit=2, window=60.0) is False

        assert await limiter.check("bucket:high", limit=10, window=60.0) is True

    @pytest.mark.anyio
    async def test_does_not_block_large_window(self, limiter) -> None:
        for _ in range(100):
            ok = await limiter.check("bucket:big", limit=100, window=3600.0)
            assert ok is True
