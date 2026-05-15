from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.errors import PluginError
from app.event_model import MessageSender, NormalizedEvent


@dataclass
class PluginResult:
    text: str | None = None
    reactions: list[str] | None = None
    data: dict[str, Any] | None = None


@dataclass
class PluginHelp:
    command: str
    description: str
    usage: str | None = None
    category: str = "通用"


@dataclass
class PluginContext:
    event: NormalizedEvent
    sender: MessageSender
    config: dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("qq_ai_bot.plugin")
    )


class BotPlugin(ABC):
    @abstractmethod
    def match(self, event: NormalizedEvent) -> bool:
        ...

    @abstractmethod
    async def handle(self, ctx: PluginContext) -> PluginResult:
        ...

    def help(self) -> PluginHelp | None:
        return None


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[BotPlugin] = []

    def register(self, plugin: BotPlugin) -> None:
        if any(p is plugin for p in self._plugins):
            raise PluginError(f"Plugin already registered: {type(plugin).__name__}")
        self._plugins.append(plugin)

    def get_all(self) -> list[BotPlugin]:
        return list(self._plugins)

    def get_help_entries(self) -> list[PluginHelp]:
        entries: list[PluginHelp] = []
        for plugin in self._plugins:
            help_info = plugin.help()
            if help_info is not None:
                entries.append(help_info)
        return entries
