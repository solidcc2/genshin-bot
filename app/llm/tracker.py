from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.storage import StorageProvider

_TZ_CN = timezone(timedelta(hours=8))


def _today_cn() -> str:
    return datetime.now(_TZ_CN).date().isoformat()


class TokenUsageTracker:
    """Tracks daily and total LLM token usage via StorageProvider.

    All reads/writes are local (SQLite or memory) — no API calls to LLM providers.
    """

    _DAILY_NS = "llm_token_daily"
    _TOTAL_NS = "llm_token_total"
    _TOTAL_KEY = "cumulative"

    def __init__(
        self,
        storage: StorageProvider,
        max_per_day: int = 0,
        max_total: int = 0,
    ) -> None:
        self._storage = storage
        self._max_per_day = max_per_day
        self._max_total = max_total

    def has_limits(self) -> bool:
        return self._max_per_day > 0 or self._max_total > 0

    async def has_capacity(self) -> bool:
        """Return True if still under all configured limits."""
        if not self.has_limits():
            return True
        daily_key = _today_cn()
        if self._max_per_day > 0:
            used = await self._storage.get(self._DAILY_NS, daily_key) or 0
            if used >= self._max_per_day:
                return False
        if self._max_total > 0:
            used = await self._storage.get(self._TOTAL_NS, self._TOTAL_KEY) or 0
            if used >= self._max_total:
                return False
        return True

    async def record(self, tokens: int) -> None:
        """Record token usage after a successful LLM call."""
        daily_key = _today_cn()
        daily_used = await self._storage.get(self._DAILY_NS, daily_key) or 0
        await self._storage.set(self._DAILY_NS, daily_key, daily_used + tokens)

        total_used = await self._storage.get(self._TOTAL_NS, self._TOTAL_KEY) or 0
        await self._storage.set(self._TOTAL_NS, self._TOTAL_KEY, total_used + tokens)

    async def daily_usage(self) -> int:
        return await self._storage.get(self._DAILY_NS, _today_cn()) or 0

    async def total_usage(self) -> int:
        return await self._storage.get(self._TOTAL_NS, self._TOTAL_KEY) or 0
