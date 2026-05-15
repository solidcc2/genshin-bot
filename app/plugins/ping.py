from __future__ import annotations

from app.plugin import BotPlugin, PluginContext, PluginHelp, PluginResult


class PingPlugin(BotPlugin):
    command = "ping"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        return PluginResult(text="Pong!")

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/ping",
            description="连通性检查",
            usage="/ping",
        )
