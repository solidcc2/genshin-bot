from __future__ import annotations

from app.event_model import MessageSender, NormalizedEvent
from app.plugin import BotPlugin, PluginContext, PluginResult, PluginRegistry


class Router:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def register(self, plugin: BotPlugin) -> None:
        self._registry.register(plugin)

    async def dispatch(
        self,
        event: NormalizedEvent,
        sender: MessageSender,
    ) -> PluginResult:
        for plugin in self._registry.get_all():
            if plugin.match(event):
                ctx = PluginContext(event=event, sender=sender)
                return await plugin.handle(ctx)
        return PluginResult(text="未知命令。输入 /help 查看可用命令。")
