from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from app.errors import LLMError
from app.event_model import NormalizedEvent, Scene
from app.llm.context import ContextBuilder
from app.llm.provider import ModelProvider
from app.llm.routing import ModelRouter
from app.llm.tracker import TokenUsageTracker
from app.plugin import BotPlugin, PluginContext, PluginResult

if TYPE_CHECKING:
    from app.signals import SignalEvaluator
    from app.session import SessionManager

_logger = logging.getLogger(__name__)

_RESPONSE_PATTERN = re.compile(
    r"^\s*(是|否)\s*[,，]\s*\+?(\d+)\s*s\s*[,，]?\s*(.*)", re.DOTALL
)
_RELAXED_PATTERN = re.compile(r"^\s*\+?(\d+)\s*s\s*[,，]?\s*(.*)", re.DOTALL)


def _parse_response(text: str) -> tuple[bool, int, str]:
    """Parse LLM response into (should_reply, delay_seconds, content).

    Three-tier parsing:
      1. Strict: "是/否, +Ns, 内容" with Chinese/English commas
      2. Relaxed: "+Ns, 内容" (missing 是/否 prefix)
      3. Fallback: bare "否" → no reply; anything else → reply with 0 delay
    """
    raw = text.strip()
    if not raw:
        return False, 0, ""
    m = _RESPONSE_PATTERN.match(raw)
    if m:
        if m.group(1) == "否":
            return False, 0, ""
        return True, int(m.group(2)), m.group(3).strip()
    relaxed = _RELAXED_PATTERN.match(raw)
    if relaxed:
        return True, int(relaxed.group(1)), relaxed.group(2).strip()
    if raw == "否":
        return False, 0, ""
    return True, 0, raw


class ChatPlugin(BotPlugin):
    command = ""

    def __init__(
        self,
        provider: ModelProvider,
        session_manager: SessionManager,
        context_builder: ContextBuilder,
        router: ModelRouter,
        tracker: TokenUsageTracker | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        signal_evaluator: SignalEvaluator | None = None,
        max_response_delay: int = 20,
    ) -> None:
        self._provider = provider
        self._session_manager = session_manager
        self._context_builder = context_builder
        self._router = router
        self._tracker = tracker
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._signal_evaluator = signal_evaluator
        self._max_response_delay = max_response_delay

    def match(self, event: NormalizedEvent) -> bool:
        return not event.text.strip().startswith("/")

    async def handle(self, ctx: PluginContext) -> PluginResult:
        # Gate: only GROUP/GUILD scenes check the signal evaluator
        if ctx.event.scene != Scene.PRIVATE and self._signal_evaluator is not None:
            if not self._signal_evaluator.should_respond(ctx.event):
                return PluginResult()  # empty → sender sends nothing
        chat_id = ctx.event.chat_id
        user_text = ctx.event.text.strip()

        if self._tracker is not None and not await self._tracker.has_capacity():
            _logger.info("llm token limit reached for chat=%s", chat_id)
            return PluginResult(text="今日对话额度已用尽，明天再来吧。")

        session = await self._session_manager.get_or_create(chat_id)
        cursor_msg_id = session.state.get("llm_context_since_msg")
        llm_messages = await self._context_builder.build(ctx.event, cursor_msg_id=cursor_msg_id)
        _logger.debug("llm prompt for chat=%s: %s", chat_id, llm_messages)
        model = self._router.select_model(user_text)

        try:
            result = await self._provider.generate(
                llm_messages,
                model=model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except LLMError as exc:
            _logger.warning("llm generation failed for chat=%s: %s", chat_id, exc)
            return PluginResult(text=f"抱歉，我现在无法回答。{exc}")

        _logger.info("llm raw response for chat=%s: %s", chat_id, result.text)

        if self._tracker is not None:
            await self._tracker.record(result.usage.total_tokens)

        cost = self._provider.estimate_cost(result.usage)
        _logger.info(
            "llm chat=%s model=%s tokens=%d(prompt=%d+completion=%d) cost=%.6f latency=%dms",
            chat_id,
            model,
            result.usage.total_tokens,
            result.usage.prompt_tokens,
            result.usage.completion_tokens,
            cost,
            result.usage.latency_ms,
        )

        text = result.text or ""
        reply, delay, reply_content = _parse_response(text)
        if not reply or not reply_content:
            return PluginResult()

        if delay > 0:
            clamped = min(delay, self._max_response_delay)
            if clamped != delay:
                _logger.info("response delay clamped %ds -> %ds for chat=%s", delay, clamped, chat_id)
            await asyncio.sleep(clamped)

        return PluginResult(text=reply_content)
