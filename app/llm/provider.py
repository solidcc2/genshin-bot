from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.errors import LLMAPIError
from app.llm.models import LLMMessage, LLMResult, UsageStats

_logger = logging.getLogger(__name__)

_COST_TABLE: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.14e-6, "output": 0.28e-6},
    "deepseek-v4-pro": {"input": 0.435e-6, "output": 0.87e-6},
}


class ModelProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        ...

    @staticmethod
    def estimate_cost(usage: UsageStats) -> float:
        ...


class DeepSeekProvider(ModelProvider):
    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://api.deepseek.com/chat/completions",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        model = model or "deepseek-v4-flash"
        payload = self._build_payload(messages, model, temperature, max_tokens)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        data = await self._post_with_retry(payload, headers)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        choice = data["choices"][0]
        usage_raw = data["usage"]
        usage = UsageStats(
            prompt_tokens=usage_raw["prompt_tokens"],
            completion_tokens=usage_raw["completion_tokens"],
            total_tokens=usage_raw["total_tokens"],
            latency_ms=elapsed_ms,
            model=model,
        )
        return LLMResult(
            text=choice["message"]["content"].strip(),
            usage=usage,
            model_used=model,
            finish_reason=choice.get("finish_reason", ""),
        )

    def _build_payload(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    async def _post_with_retry(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.post(self._endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if attempt < self._max_retries and status in (429, 500, 502, 503):
                    wait = 2**attempt
                    _logger.warning(
                        "llm api attempt %d failed status=%d, retrying in %ds",
                        attempt + 1, status, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise LLMAPIError(f"API error: {status} {exc.response.text}") from exc
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    wait = 2**attempt
                    _logger.warning(
                        "llm request attempt %d failed: %s, retrying in %ds",
                        attempt + 1, exc, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise LLMAPIError(f"Request failed after {self._max_retries} retries: {exc}") from exc
        raise LLMAPIError(f"Request failed after {self._max_retries} retries") from last_exc

    @staticmethod
    def estimate_cost(usage: UsageStats) -> float:
        rates = _COST_TABLE.get(usage.model, _COST_TABLE["deepseek-v4-flash"])
        return usage.prompt_tokens * rates["input"] + usage.completion_tokens * rates["output"]

    async def close(self) -> None:
        await self._client.aclose()
