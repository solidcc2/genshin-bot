from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.plugin import PluginContext
from app.plugins.genshin import (
    HoyobindPlugin,
    HoyounbindPlugin,
    NotesPlugin,
    SignPlugin,
    StatsPlugin,
)
from app.providers.hoyolab.models import (
    ChronicleData,
    ChronicleResult,
    NotesData,
    NotesResult,
    QRLoginSession,
    QRLoginStatus,
    SignResult,
    CheckInResult,
)
from conftest import FakeSender, make_event


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.is_bound = AsyncMock(return_value=False)
    p.start_qr_login = AsyncMock(
        return_value=QRLoginSession(
            ticket="test_ticket",
            qr_url="https://example.com/qr",
            qr_image=b"fake_png",
            status=QRLoginStatus.WAITING,
        )
    )
    p.poll_qr_login = AsyncMock(
        return_value=QRLoginSession(
            ticket="test_ticket",
            qr_url="",
            qr_image=b"",
            status=QRLoginStatus.CONFIRMED,
            cookies={"ltoken": "abc", "ltuid": "123"},
        )
    )
    p.unbind = AsyncMock()
    p.bind = AsyncMock()

    p.get_notes = AsyncMock(
        return_value=NotesResult(
            data=NotesData(
                current_resin=120,
                max_resin=160,
                resin_recovery_time="",
                current_expeditions=3,
                max_expeditions=5,
                current_daily_task=2,
                max_daily_task=4,
            )
        )
    )

    p.daily_sign = AsyncMock(
        return_value=SignResult(data=CheckInResult(success=True, message="签到成功"))
    )

    p.get_battle_chronicle = AsyncMock(
        return_value=ChronicleResult(
            data=ChronicleData(
                uid="123456789",
                region="cn",
            )
        )
    )
    return p


class TestHoyobindPlugin:
    @pytest.mark.anyio
    async def test_match(self) -> None:
        plugin = HoyobindPlugin(AsyncMock())
        assert plugin.match(make_event("/hoyobind"))
        assert plugin.match(make_event("/hoyobind abc"))
        assert not plugin.match(make_event("hoyobind"))

    @pytest.mark.anyio
    async def test_handle_already_bound(self, mock_provider) -> None:
        mock_provider.is_bound = AsyncMock(return_value=True)
        plugin = HoyobindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyobind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "已经绑定" in result.text

    @pytest.mark.anyio
    async def test_handle_success(self, mock_provider) -> None:
        plugin = HoyobindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyobind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "绑定成功" in result.text
        mock_provider.bind.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_canceled(self, mock_provider) -> None:
        mock_provider.poll_qr_login = AsyncMock(
            return_value=QRLoginSession(
                ticket="t", qr_url="", qr_image=b"",
                status=QRLoginStatus.CANCELED,
            )
        )
        plugin = HoyobindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyobind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "取消" in result.text

    @pytest.mark.anyio
    async def test_handle_expired(self, mock_provider) -> None:
        mock_provider.poll_qr_login = AsyncMock(
            return_value=QRLoginSession(
                ticket="t", qr_url="", qr_image=b"",
                status=QRLoginStatus.EXPIRED,
            )
        )
        plugin = HoyobindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyobind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "过期" in result.text

    def test_help(self) -> None:
        plugin = HoyobindPlugin(AsyncMock())
        help_info = plugin.help()
        assert help_info is not None
        assert help_info.command == "/hoyobind"


class TestHoyounbindPlugin:
    @pytest.mark.anyio
    async def test_match(self) -> None:
        plugin = HoyounbindPlugin(AsyncMock())
        assert plugin.match(make_event("/hoyounbind"))
        assert plugin.match(make_event("/hoyounbind extra"))
        assert not plugin.match(make_event("hoyounbind"))

    @pytest.mark.anyio
    async def test_handle_not_bound(self, mock_provider) -> None:
        plugin = HoyounbindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyounbind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "没有绑定" in result.text

    @pytest.mark.anyio
    async def test_handle_success(self, mock_provider) -> None:
        mock_provider.is_bound = AsyncMock(return_value=True)
        plugin = HoyounbindPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/hoyounbind"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "已解绑" in result.text
        mock_provider.unbind.assert_called_once()

    def test_help(self) -> None:
        plugin = HoyounbindPlugin(AsyncMock())
        help_info = plugin.help()
        assert help_info is not None
        assert help_info.command == "/hoyounbind"


class TestNotesPlugin:
    @pytest.mark.anyio
    async def test_match(self) -> None:
        plugin = NotesPlugin(AsyncMock())
        assert plugin.match(make_event("/notes"))
        assert plugin.match(make_event("/notes extra"))
        assert not plugin.match(make_event("notes"))

    @pytest.mark.anyio
    async def test_handle(self, mock_provider) -> None:
        plugin = NotesPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/notes"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "120" in result.text  # resin
        assert "3" in result.text   # expeditions
        assert "2/4" in result.text  # daily task

    @pytest.mark.anyio
    async def test_handle_error(self, mock_provider) -> None:
        mock_provider.get_notes = AsyncMock(
            return_value=NotesResult(error="API unavailable")
        )
        plugin = NotesPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/notes"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "失败" in result.text or "unavailable" in result.text

    def test_help(self) -> None:
        plugin = NotesPlugin(AsyncMock())
        help_info = plugin.help()
        assert help_info is not None
        assert help_info.command == "/notes"


class TestSignPlugin:
    @pytest.mark.anyio
    async def test_match(self) -> None:
        plugin = SignPlugin(AsyncMock())
        assert plugin.match(make_event("/sign"))
        assert plugin.match(make_event("/sign extra"))
        assert not plugin.match(make_event("sign"))

    @pytest.mark.anyio
    async def test_handle(self, mock_provider) -> None:
        plugin = SignPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/sign"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "签到成功" in result.text

    @pytest.mark.anyio
    async def test_handle_error(self, mock_provider) -> None:
        mock_provider.daily_sign = AsyncMock(
            return_value=SignResult(error="sign failed")
        )
        plugin = SignPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/sign"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "失败" in result.text

    def test_help(self) -> None:
        plugin = SignPlugin(AsyncMock())
        help_info = plugin.help()
        assert help_info is not None
        assert help_info.command == "/sign"


class TestStatsPlugin:
    @pytest.mark.anyio
    async def test_match(self) -> None:
        plugin = StatsPlugin(AsyncMock())
        assert plugin.match(make_event("/stats"))
        assert plugin.match(make_event("/stats 123456789"))
        assert not plugin.match(make_event("stats"))

    @pytest.mark.anyio
    async def test_handle(self, mock_provider) -> None:
        plugin = StatsPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/stats"), sender=FakeSender()
        ))
        assert result.text is not None

    @pytest.mark.anyio
    async def test_handle_error(self, mock_provider) -> None:
        mock_provider.get_battle_chronicle = AsyncMock(
            return_value=ChronicleResult(error="query failed")
        )
        plugin = StatsPlugin(mock_provider)
        result = await plugin.handle(PluginContext(
            event=make_event("/stats"), sender=FakeSender()
        ))
        assert result.text is not None
        assert "失败" in result.text

    def test_help(self) -> None:
        plugin = StatsPlugin(AsyncMock())
        help_info = plugin.help()
        assert help_info is not None
        assert help_info.command == "/stats"
