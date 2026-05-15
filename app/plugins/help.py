from __future__ import annotations

from app.plugin import BotPlugin, PluginContext, PluginHelp, PluginResult, PluginRegistry


class HelpPlugin(BotPlugin):
    command = "help"

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    async def handle(self, ctx: PluginContext) -> PluginResult:
        entries = self._registry.get_help_entries()
        if not entries:
            return PluginResult(text="没有已注册的插件。")

        groups: dict[str, list[PluginHelp]] = {}
        for entry in entries:
            groups.setdefault(entry.category, []).append(entry)

        lines = ["可用命令："]
        for category in sorted(groups, key=lambda c: (c != "通用", c)):
            # 排序：非"通用"分类按字母序在前，"通用"分类始终最后
            items = groups[category]
            lines.append(f"\n[{category}]")
            for entry in items:
                usage = f" {entry.usage}" if entry.usage else ""
                lines.append(f"  {entry.command} — {entry.description}{usage}")

        return PluginResult(text="\n".join(lines))

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/help",
            description="显示可用命令列表",
            usage="/help",
        )
