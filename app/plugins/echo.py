from __future__ import annotations

from app.plugin import BotPlugin, PluginContext, PluginHelp, PluginResult


class EchoPlugin(BotPlugin):
    command = "echo"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        return PluginResult(text=self._extract_args(ctx.event.text))

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/echo",
            description="回显消息内容",
            usage="/echo <text>",
        )
