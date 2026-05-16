import httpx
import pytest

from app.errors import LLMAPIError
from app.llm.models import LLMMessage
from app.llm.provider import DeepSeekProvider


@pytest.mark.anyio
class TestDeepSeekProvider:
    def _make_provider(self, api_key="sk-test") -> DeepSeekProvider:
        return DeepSeekProvider(api_key=api_key)

    async def test_build_payload(self) -> None:
        provider = self._make_provider()
        messages = [LLMMessage(role="user", content="hello")]
        payload = provider._build_payload(messages, "deepseek-v4-flash", 0.7, 2048)
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2048

    async def test_build_payload_minimal(self) -> None:
        provider = self._make_provider()
        messages = [LLMMessage(role="user", content="hi")]
        payload = provider._build_payload(messages, "deepseek-v4-flash", None, None)
        assert "temperature" not in payload
        assert "max_tokens" not in payload

    async def test_estimate_cost_flash(self) -> None:
        from app.llm.models import UsageStats
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=100, model="deepseek-v4-flash")
        cost = DeepSeekProvider.estimate_cost(usage)
        expected = 100 * 0.14e-6 + 50 * 0.28e-6
        assert cost == pytest.approx(expected)

    async def test_estimate_cost_pro(self) -> None:
        from app.llm.models import UsageStats
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=100, model="deepseek-v4-pro")
        cost = DeepSeekProvider.estimate_cost(usage)
        expected = 100 * 0.435e-6 + 50 * 0.87e-6
        assert cost == pytest.approx(expected)

    async def test_estimate_cost_unknown_model(self) -> None:
        from app.llm.models import UsageStats
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=100, model="unknown")
        cost = DeepSeekProvider.estimate_cost(usage)
        expected = 100 * 0.14e-6 + 50 * 0.28e-6  # falls back to flash
        assert cost == pytest.approx(expected)
