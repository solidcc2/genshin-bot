from app.event_model import NormalizedEvent
from app.plugin import BotPlugin, PluginContext, PluginResult


class NullPlugin(BotPlugin):
    """Catch-all plugin that returns an empty result.

    Registered last in the plugin chain. Each adapter decides how
    to handle PluginResult(text=None) — CLI falls back to the
    "unknown command" hint, OneBot silently ignores it.
    """

    def match(self, event: NormalizedEvent) -> bool:
        return True

    async def handle(self, ctx: PluginContext) -> PluginResult:
        return PluginResult()
