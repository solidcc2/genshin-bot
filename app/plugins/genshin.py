from __future__ import annotations

import logging

from app.config import HoYoLABConfig
from app.errors import NotBoundError
from app.event_model import NormalizedEvent
from app.plugin import BotPlugin, PluginContext, PluginHelp, PluginResult
from app.providers.hoyolab import HoYoLABProvider
from app.providers.hoyolab.models import QRLoginStatus
from app.router import Router
from app.storage import StorageProvider


class HoyobindPlugin(BotPlugin):
    """QR code login to bind HoYoLAB cookies."""

    def __init__(self, provider: HoYoLABProvider) -> None:
        self._provider = provider

    def match(self, event: NormalizedEvent) -> bool:
        return event.text.strip() == "/hoyobind"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        user_id = ctx.event.user_id

        if await self._provider.is_bound(user_id):
            return PluginResult(text="你已经绑定了米游社账号")

        session = await self._provider.start_qr_login()

        lines = [
            "请使用手机 HoYoLAB 扫码登录",
            f"正在等待扫码...（超时 {int(self._provider.qr_timeout)} 秒）",
        ]
        if session.qr_path:
            lines.append(f"二维码已保存至: {session.qr_path}")
        await ctx.sender.send_reply(ctx.event, "\n".join(lines))

        result = await self._provider.poll_qr_login(
            session.ticket, session.device_id, timeout=self._provider.qr_timeout
        )

        if result.status == QRLoginStatus.CONFIRMED and result.cookies:
            await self._provider.bind(user_id, result.cookies)
            return PluginResult(text="绑定成功！")
        elif result.status == QRLoginStatus.CANCELED:
            return PluginResult(text="扫码已取消")
        elif result.status == QRLoginStatus.EXPIRED:
            return PluginResult(text="二维码已过期，请重新使用 /hoyobind")
        else:
            return PluginResult(text=f"登录失败，状态: {result.status.value}")

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/hoyobind",
            description="扫码绑定米游社账号",
            usage="/hoyobind",
            category="米游社",
        )


class HoyounbindPlugin(BotPlugin):
    """Unbind HoYoLAB cookies."""

    def __init__(self, provider: HoYoLABProvider) -> None:
        self._provider = provider

    def match(self, event: NormalizedEvent) -> bool:
        return event.text.strip() == "/hoyounbind"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        if not await self._provider.is_bound(ctx.event.user_id):
            return PluginResult(text="你还没有绑定米游社账号")
        await self._provider.unbind(ctx.event.user_id)
        return PluginResult(text="已解绑")

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/hoyounbind",
            description="解绑米游社账号",
            usage="/hoyounbind",
            category="米游社",
        )


class NotesPlugin(BotPlugin):
    """Real-time notes (resin, expeditions, etc.)."""

    def __init__(self, provider: HoYoLABProvider) -> None:
        self._provider = provider

    def match(self, event: NormalizedEvent) -> bool:
        return event.text.strip() == "/notes"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        try:
            result = await self._provider.get_notes(ctx.event.user_id)
        except NotBoundError as exc:
            return PluginResult(text=str(exc))

        if result.error:
            return PluginResult(text=f"获取便笺失败: {result.error}")
        if not result.data:
            return PluginResult(text="无法获取便笺数据")

        d = result.data
        lines = [
            f"树脂: {d.resin_display}",
            f"派遣: {d.expedition_display}",
            f"每日: {d.current_daily_task}/{d.max_daily_task}",
        ]
        return PluginResult(text="\n".join(lines))

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/notes",
            description="查看实时便笺（树脂、派遣、每日）",
            usage="/notes",
            category="米游社",
        )


class SignPlugin(BotPlugin):
    """Daily check-in."""

    def __init__(self, provider: HoYoLABProvider) -> None:
        self._provider = provider

    def match(self, event: NormalizedEvent) -> bool:
        return event.text.strip() == "/sign"

    async def handle(self, ctx: PluginContext) -> PluginResult:
        try:
            result = await self._provider.daily_sign(ctx.event.user_id)
        except NotBoundError as exc:
            return PluginResult(text=str(exc))

        if result.error:
            return PluginResult(text=f"签到失败: {result.error}")
        if result.data:
            return PluginResult(text=result.data.message)
        return PluginResult(text="签到失败，未知错误")

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/sign",
            description="米游社每日签到",
            usage="/sign",
            category="米游社",
        )


class StatsPlugin(BotPlugin):
    """Battle chronicle summary."""

    def __init__(self, provider: HoYoLABProvider) -> None:
        self._provider = provider

    def match(self, event: NormalizedEvent) -> bool:
        text = event.text.strip()
        if text == "/stats":
            return True
        if text.startswith("/stats "):
            return True
        return False

    async def handle(self, ctx: PluginContext) -> PluginResult:
        parts = ctx.event.text.strip().split(maxsplit=1)
        uid = parts[1] if len(parts) > 1 else None

        try:
            result = await self._provider.get_battle_chronicle(ctx.event.user_id, uid=uid)
        except NotBoundError as exc:
            return PluginResult(text=str(exc))

        if result.error:
            return PluginResult(text=f"查询失败: {result.error}")
        if not result.data:
            return PluginResult(text="无法获取战绩数据")

        d = result.data
        lines = [f"UID: {d.uid}", f"区域: {d.region}"]
        return PluginResult(text="\n".join(lines))

    def help(self) -> PluginHelp:
        return PluginHelp(
            command="/stats",
            description="查询战绩摘要",
            usage="/stats [uid]",
            category="米游社",
        )


def register(
    router: Router,
    storage: StorageProvider,
    hoyolab_config: HoYoLABConfig,
) -> HoYoLABProvider | None:
    """Instantiate HoYoLABProvider and register all hoyolab plugins."""
    try:
        provider = HoYoLABProvider(
            storage=storage,
            region=hoyolab_config.region,
            qr_timeout=hoyolab_config.qr_timeout,
        )
    except Exception:
        logging.getLogger(__name__).warning("failed to initialize hoyolab provider")
        return None

    plugins: tuple[BotPlugin, ...] = (
        HoyobindPlugin(provider),
        HoyounbindPlugin(provider),
        NotesPlugin(provider),
        SignPlugin(provider),
        StatsPlugin(provider),
    )
    for plugin in plugins:
        router.register(plugin)

    return provider
