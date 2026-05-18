from __future__ import annotations

from typing import TYPE_CHECKING

from app.event_model import NormalizedEvent
from app.plugin import BotPlugin, PluginContext, PluginHelp, PluginResult

if TYPE_CHECKING:
    from app.session import SessionManager


class LLMRefreshEnvPlugin(BotPlugin):
    command = ""

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def match(self, event: NormalizedEvent) -> bool:
        return event.text.strip() == "/llm-refresh-env"

    def help(self) -> PluginHelp | None:
        return PluginHelp(
            command="llm-refresh-env",
            description="重置 LLM 环境上下文，清空对话历史并移动可见游标",
            category="通用",
        )

    async def handle(self, ctx: PluginContext) -> PluginResult:
        session = await self._session_manager.get_or_create(ctx.event.chat_id)
        session.messages.clear()
        session.state.clear()
        session.state["llm_context_since_msg"] = ctx.event.message_id
        await self._session_manager.save(session)
        return PluginResult(text="聊天上下文已重置。")
