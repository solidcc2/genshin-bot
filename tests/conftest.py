from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.event_model import NormalizedEvent, Scene  # noqa: E402


def make_event(text: str, **overrides) -> NormalizedEvent:
    kwargs = dict(
        platform="test",
        adapter="test",
        scene=Scene.PRIVATE,
        chat_id="chat_001",
        user_id="user_001",
        message_id="msg_001",
        text=text,
    )
    kwargs.update(overrides)
    return NormalizedEvent(**kwargs)


class FakeSender:
    async def send_text(self, target, text: str) -> str:
        return "fake_id"

    async def send_reply(self, event, text: str) -> str:
        return "fake_id"

    async def send_image(self, target, image_data: bytes) -> str:
        return "fake_image_id"

    async def send_reply_image(self, event, image_data: bytes) -> str:
        return "fake_image_id"

    async def recall(self, message_id: str) -> bool:
        return False


class FakeModelProvider:
    def __init__(self, response: str | None = None) -> None:
        self.last_messages: list | None = None
        self.last_model: str | None = None
        self._response = response or "你好！有什么可以帮助你的？"
        self.call_count = 0

    async def generate(self, messages, model=None, **kwargs):
        self.last_messages = messages
        self.last_model = model
        self.call_count += 1
        from app.llm.models import LLMResult, UsageStats
        return LLMResult(
            text=self._response,
            usage=UsageStats(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                latency_ms=100,
                model=model or "deepseek-v4-flash",
            ),
            model_used=model or "deepseek-v4-flash",
            finish_reason="stop",
        )

    @staticmethod
    def estimate_cost(usage) -> float:
        return 0.001
