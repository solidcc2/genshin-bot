from __future__ import annotations

from app.event_model import NormalizedEvent
from app.llm.models import LLMMessage
from app.plugin import PluginRegistry
from app.session import Session


class ContextBuilder:
    def __init__(self, persona: str, plugin_registry: PluginRegistry) -> None:
        self._persona = persona
        self._registry = plugin_registry

    def build(self, session: Session, event: NormalizedEvent) -> list[LLMMessage]:
        messages: list[LLMMessage] = []

        # Layer 0: 人设
        messages.append(LLMMessage(role="system", content=self._persona))

        # Layer 1: 技能声明（自动从 PluginRegistry 聚合）
        skills = self._registry.get_help_entries()
        if skills:
            skill_lines = ["可用命令："]
            for s in skills:
                skill_lines.append(f"{s.command} — {s.description}")
            messages.append(LLMMessage(role="system", content="\n".join(skill_lines)))

        # Layer 2: 会话历史
        for msg in session.messages:
            messages.append(LLMMessage(role=msg.role, content=msg.text))  # type: ignore[arg-type]

        # Layer 3: 当前输入
        messages.append(LLMMessage(role="user", content=event.text))

        return messages
