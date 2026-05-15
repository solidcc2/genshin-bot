from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import genshin
import pytest
from genshin import AlreadyClaimed, GenshinException

from app.providers.hoyolab import HoYoLABProvider
from app.providers.hoyolab.models import QRLoginSession, QRLoginStatus
from app.storage.memory import MemoryStorage

REGION = "cn"
QR_TIMEOUT = 120.0


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def mock_client():
    with patch("genshin.Client") as mock_cls:
        client = AsyncMock()
        client.close = AsyncMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture
def provider(storage, mock_client):
    return HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)


class TestQRLogin:
    @pytest.mark.anyio
    async def test_start_qrcode(self, provider, mock_client) -> None:
        from genshin.models.auth import QRCodeCreationResult

        mock_client._create_qrcode = AsyncMock(
            return_value=QRCodeCreationResult(
                ticket="ticket_123", url="https://example.com/qr"
            )
        )

        with patch("app.providers.hoyolab.qrcode.make") as mock_make, \
             patch("app.providers.hoyolab.io.BytesIO") as mock_bytesio:
            mock_img = MagicMock()
            mock_img.save.return_value = None
            mock_make.return_value = mock_img
            mock_buf = MagicMock()
            mock_buf.getvalue.return_value = b"fake_png"
            mock_bytesio.return_value = mock_buf

            session = await provider.start_qr_login()

        assert session.ticket == "ticket_123"
        assert session.qr_url == "https://example.com/qr"
        assert session.status == QRLoginStatus.WAITING
        assert len(session.qr_image) > 0
        assert session.device_id != ""

    @pytest.mark.anyio
    async def test_poll_qrcode_confirmed(self, provider, mock_client) -> None:
        from genshin.client.components.auth.subclients.app import QRCodeStatus

        mock_resp_cookies = MagicMock()
        mock_resp_cookies.items.return_value = [
            ("ltoken_v2", MagicMock(value="val_ltoken_v2")),
            ("ltuid_v2", MagicMock(value="12345")),
        ]

        mock_client._check_qrcode = AsyncMock(
            return_value=(QRCodeStatus.CONFIRMED, mock_resp_cookies)
        )

        session = await provider.poll_qr_login("ticket_123", "dev123", timeout=10.0)

        assert session.status == QRLoginStatus.CONFIRMED
        assert session.cookies == {"ltoken_v2": "val_ltoken_v2", "ltuid_v2": "12345"}

    @pytest.mark.anyio
    async def test_poll_qrcode_expired_via_exception(self, provider, mock_client) -> None:
        mock_client._check_qrcode = AsyncMock(
            side_effect=GenshinException({"retcode": -106, "message": "QR expired"})
        )

        session = await provider.poll_qr_login("ticket_123", "dev123", timeout=10.0)

        assert session.status == QRLoginStatus.EXPIRED

    @pytest.mark.anyio
    async def test_poll_qrcode_timeout(self, provider, mock_client) -> None:
        from genshin.client.components.auth.subclients.app import QRCodeStatus

        mock_client._check_qrcode = AsyncMock(
            return_value=(QRCodeStatus.CREATED, MagicMock())
        )

        session = await provider.poll_qr_login("ticket_123", "dev123", timeout=0.1)

        assert session.status == QRLoginStatus.EXPIRED

    @pytest.mark.anyio
    async def test_poll_qrcode_canceled_via_status(self, provider, mock_client) -> None:
        """ValueError from QRCodeStatus constructor maps to CANCELED."""
        mock_client._check_qrcode = AsyncMock(side_effect=ValueError("Canceled"))

        session = await provider.poll_qr_login("ticket_123", "dev123", timeout=10.0)

        assert session.status == QRLoginStatus.CANCELED

    @pytest.mark.anyio
    async def test_poll_qrcode_canceled_via_exception(self, provider, mock_client) -> None:
        """GenshinException with retcode != -106 maps to CANCELED."""
        mock_client._check_qrcode = AsyncMock(
            side_effect=GenshinException({"retcode": -107, "message": "QR cancelled"})
        )

        session = await provider.poll_qr_login("ticket_123", "dev123", timeout=10.0)

        assert session.status == QRLoginStatus.CANCELED


class TestNotes:
    @pytest.mark.anyio
    async def test_get_notes_success(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_genshin_notes = MagicMock()
        mock_genshin_notes.current_resin = 120
        mock_genshin_notes.max_resin = 160
        mock_genshin_notes.remaining_resin_recovery_time = "00:00:00"
        mock_genshin_notes.expeditions = [MagicMock(), MagicMock(), MagicMock()]
        mock_genshin_notes.max_expeditions = 5
        mock_genshin_notes.completed_commissions = 2
        mock_genshin_notes.max_commissions = 4

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_notes = AsyncMock(return_value=mock_genshin_notes)
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_notes("user_001")

        assert result.error is None
        assert result.data is not None
        assert result.data.current_resin == 120
        assert result.data.max_resin == 160
        assert result.data.resin_display == "120/160"
        assert result.data.current_expeditions == 3
        assert result.data.max_expeditions == 5
        assert result.data.expedition_display == "3/5"
        assert result.data.current_daily_task == 2
        assert result.data.max_daily_task == 4

    @pytest.mark.anyio
    async def test_get_notes_api_error(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_notes = AsyncMock(
                side_effect=GenshinException({"retcode": -100, "message": "invalid cookie"})
            )
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_notes("user_001")

        assert result.data is None
        assert result.error is not None

    @pytest.mark.anyio
    async def test_get_notes_not_bound(self, provider) -> None:
        from app.errors import NotBoundError

        with pytest.raises(NotBoundError):
            await provider.get_notes("user_001")


class TestDailySign:
    @pytest.mark.anyio
    async def test_sign_success(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_info = MagicMock()
        mock_info.signed_in = False

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_reward_info = AsyncMock(return_value=mock_info)
            client.claim_daily_reward = AsyncMock()
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.daily_sign("user_001")

        assert result.error is None
        assert result.data is not None
        assert result.data.success is True
        assert "签到成功" in result.data.message

    @pytest.mark.anyio
    async def test_sign_already_signed(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_info = MagicMock()
        mock_info.signed_in = True

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_reward_info = AsyncMock(return_value=mock_info)
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.daily_sign("user_001")

        assert result.error is None
        assert result.data is not None
        assert result.data.today_signed is True
        assert "已签到" in result.data.message

    @pytest.mark.anyio
    async def test_sign_already_claimed_exception(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_info = MagicMock()
        mock_info.signed_in = False

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_reward_info = AsyncMock(return_value=mock_info)
            client.claim_daily_reward = AsyncMock(
                side_effect=AlreadyClaimed({"retcode": -5003, "message": "Already claimed"})
            )
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.daily_sign("user_001")

        assert result.error is None
        assert result.data is not None
        assert result.data.today_signed is True
        assert "已签到" in result.data.message

    @pytest.mark.anyio
    async def test_sign_api_error(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_reward_info = AsyncMock(
                side_effect=GenshinException({"retcode": -100, "message": "invalid cookie"})
            )
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.daily_sign("user_001")

        assert result.data is None
        assert result.error is not None


class TestBattleChronicle:
    @pytest.mark.anyio
    async def test_chronicle_success(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_info = MagicMock()
        mock_info.uid = 123456789

        mock_user = MagicMock()
        mock_user.info = mock_info

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_genshin_user = AsyncMock(return_value=mock_user)
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_battle_chronicle("user_001")

        assert result.error is None
        assert result.data is not None
        assert result.data.uid == "123456789"

    @pytest.mark.anyio
    async def test_chronicle_with_uid(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        mock_info = MagicMock()
        mock_info.uid = 987654321

        mock_user = MagicMock()
        mock_user.info = mock_info

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_genshin_user = AsyncMock(return_value=mock_user)
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_battle_chronicle("user_001", uid="987654321")

        assert result.error is None
        assert result.data is not None
        assert result.data.uid == "987654321"
        client.get_genshin_user.assert_called_with(uid=987654321)

    @pytest.mark.anyio
    async def test_chronicle_geetest_error(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_genshin_user = AsyncMock(
                side_effect=__import__("genshin").GeetestError({"retcode": 1034, "message": "triggered"})
            )
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_battle_chronicle("user_001")

        assert result.data is None
        assert result.error is not None
        assert "风控" in result.error

    @pytest.mark.anyio
    async def test_chronicle_api_error(self, storage) -> None:
        await storage.set("hoyolab", "user_001", {"cookies": {"ltoken_v2": "abc"}, "uid": "123456789"})

        with patch("genshin.Client") as mock_cls:
            client = MagicMock()
            client.get_genshin_user = AsyncMock(
                side_effect=GenshinException({"retcode": -100, "message": "invalid cookie"})
            )
            client.close = AsyncMock()
            mock_cls.return_value = client
            provider = HoYoLABProvider(storage=storage, region=REGION, qr_timeout=QR_TIMEOUT)

            result = await provider.get_battle_chronicle("user_001")

        assert result.data is None
        assert result.error is not None


class TestBound:
    @pytest.mark.anyio
    async def test_is_bound(self, provider) -> None:
        assert await provider.is_bound("user_001") is False
        await provider.bind("user_001", {"ltoken_v2": "abc"})
        assert await provider.is_bound("user_001") is True

    @pytest.mark.anyio
    async def test_unbind(self, provider) -> None:
        await provider.bind("user_001", {"ltoken_v2": "abc"})
        assert await provider.is_bound("user_001") is True
        await provider.unbind("user_001")
        assert await provider.is_bound("user_001") is False

    @pytest.mark.anyio
    async def test_load_session(self, provider, mock_client) -> None:
        mock_account = MagicMock()
        mock_account.game = genshin.Game.GENSHIN
        mock_account.uid = 123456789
        mock_client.get_game_accounts = AsyncMock(return_value=[mock_account])

        await provider.bind("user_001", {"ltoken_v2": "abc"})
        session = await provider._load_session("user_001")
        assert session is not None
        assert session["cookies"] == {"ltoken_v2": "abc"}
        assert session["uid"] == "123456789"
        assert "device_id" in session

    @pytest.mark.anyio
    async def test_load_session_missing(self, provider) -> None:
        session = await provider._load_session("user_001")
        assert session is None
