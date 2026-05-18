from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.errors import LLMError
from app.event_model import NormalizedEvent, Scene
from app.llm.context import ContextBuilder
from app.llm.provider import ModelProvider
from app.llm.routing import ModelRouter
from app.llm.tracker import TokenUsageTracker
from app.plugin import BotPlugin, PluginContext, PluginResult
from app.session import SessionManager

if TYPE_CHECKING:
    from app.signals import SignalEvaluator

_logger = logging.getLogger(__name__)


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
    ) -> None:
        self._provider = provider
        self._session_manager = session_manager
        self._context_builder = context_builder
        self._router = router
        self._tracker = tracker
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._signal_evaluator = signal_evaluator

    def match(self, event: NormalizedEvent) -> bool:
        return not event.text.strip().startswith("/")

    async def handle(self, ctx: PluginContext) -> PluginResult:
        # Gate: only GROUP/GUILD scenes check the signal evaluator
        if ctx.event.scene != Scene.PRIVATE and self._signal_evaluator is not None:
            if not self._signal_evaluator.should_respond(ctx.event):
                return PluginResult()  # empty → sender sends nothing
        chat_id = ctx.event.chat_id
        user_text = ctx.event.text.strip()

        session = await self._session_manager.get_or_create(chat_id)

        if self._tracker is not None and not await self._tracker.has_capacity():
            _logger.info("llm token limit reached for chat=%s", chat_id)
            return PluginResult(text="今日对话额度已用尽，明天再来吧。")

        llm_messages = await self._context_builder.build(session, ctx.event)
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

        await self._session_manager.add_message(chat_id, "user", user_text)
        await self._session_manager.add_message(chat_id, "assistant", result.text)

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

        return PluginResult(text=result.text)
