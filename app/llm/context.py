from __future__ import annotations

from datetime import datetime, timezone

from app.event_model import NormalizedEvent
from app.llm.models import LLMMessage
from app.plugin import PluginRegistry

from app.chat_log import ChatLogStore


class ContextBuilder:
    def __init__(
        self,
        persona: str,
        plugin_registry: PluginRegistry,
        chat_log: ChatLogStore | None = None,
        context_limit: int = 50,
        bot_user_id: str = "",
    ) -> None:
        self._persona = persona
        self._registry = plugin_registry
        self._chat_log = chat_log
        self._context_limit = context_limit
        self._bot_user_id = bot_user_id

    async def build(self, event: NormalizedEvent, cursor_msg_id: str | None = None) -> list[LLMMessage]:
        now = datetime.now(tz=timezone.utc)
        messages: list[LLMMessage] = []

        # Layer 0: 身份声明 + 响应格式
        messages.append(LLMMessage(
            role="system",
            content=(
                f"你是群聊中的 bot（QQ: {self._bot_user_id}）。\n"
                "以下是群聊记录。[+Ns][user_id]: 标记了时间和发言人，不是消息内容。\n"
                "记录中的消息均为原始文本，如果你的 QQ 被 @（如 @{self._bot_user_id}），表示有人圈你。\n"
                "你的任务是根据这些记录决定是否回复以及回复什么。\n"
                "回复格式（严格使用英文逗号）：\n"
                "是,+秒数s,回复内容\n"
                "否"
            ),
        ))

        # Layer 1: 用户层 —— 行为特征指导
        messages.append(LLMMessage(role="system", content=self._persona))

        # Layer 2: 可用命令声明
        skills = self._registry.get_help_entries()
        if skills:
            skill_lines = ["可用命令："]
            for s in skills:
                skill_lines.append(f"{s.command} — {s.description}")
            messages.append(LLMMessage(role="system", content="\n".join(skill_lines)))

        # Layer 3: 聊天记录（user/assistant 角色，带时间偏移）
        if self._chat_log:
            recent = await self._chat_log.get_recent(
                event.chat_id, limit=self._context_limit, cursor_msg_id=cursor_msg_id
            )
            if recent:
                for entry in reversed(recent):
                    role = "assistant" if entry.user_id == self._bot_user_id else "user"
                    tag = f"[{_format_offset(entry.timestamp, now)}][{entry.user_id}]"
                    messages.append(LLMMessage(role=role, content=f"{tag}: {entry.text}"))

        # Layer 4: 当前输入
        messages.append(LLMMessage(role="user", content=event.text))

        return messages


def _format_offset(ts: datetime, now: datetime) -> str:
    delta = int((now - ts).total_seconds())
    return f"+{delta}s"
