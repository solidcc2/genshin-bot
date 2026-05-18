from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
import random
import string
from typing import TypedDict

import genshin
import qrcode
from genshin.client.components.auth.subclients.app import QRCodeStatus
from qrcode.image.pil import PilImage

from app.errors import NotBoundError
from app.providers.hoyolab.models import (
    CheckInResult,
    ChronicleData,
    ChronicleResult,
    NotesData,
    NotesResult,
    QRLoginSession,
    QRLoginStatus,
    SignResult,
)
from app.storage import StorageProvider

_NS_HOYOLAB = "hoyolab"
_REGION_MAP: dict[str, genshin.Region] = {
    "cn": genshin.Region.CHINESE,
    "os": genshin.Region.OVERSEAS,
}
_logger = logging.getLogger(__name__)


class _SessionData(TypedDict):
    cookies: dict[str, str]
    uid: str | None
    device_id: str | None
    device_fp: str | None


def _generate_device_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Mobile Safari/537.36"
)


class HoYoLABProvider:
    def __init__(
        self,
        storage: StorageProvider,
        region: str,
        qr_timeout: float,
    ) -> None:
        self._storage = storage
        self._region = _REGION_MAP.get(region, genshin.Region.CHINESE)
        self._region_str = region
        self._qr_timeout = qr_timeout
        self._client: genshin.Client | None = None

    @property
    def qr_timeout(self) -> float:
        return self._qr_timeout

    # --- auth ---

    async def start_qr_login(self) -> QRLoginSession:
        device_id = _generate_device_id()
        client = genshin.Client(region=self._region, device_id=device_id)
        creation = await client._create_qrcode()

        def _generate_qr(url: str) -> tuple[bytes, str]:
            img = qrcode.make(url, image_factory=PilImage)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qr_bytes = buf.getvalue()

            qr_path = ""
            try:
                qr_file = Path("data/qrcodes") / f"{creation.ticket}.png"
                qr_file.parent.mkdir(parents=True, exist_ok=True)
                qr_file.write_bytes(qr_bytes)
                qr_path = str(qr_file)
            except Exception as exc:
                _logger.warning("failed to save qr image: %s", exc)

            return qr_bytes, qr_path

        qr_bytes, qr_path = await asyncio.to_thread(_generate_qr, creation.url)

        return QRLoginSession(
            ticket=creation.ticket,
            qr_url=creation.url,
            qr_image=qr_bytes,
            qr_path=qr_path,
            status=QRLoginStatus.WAITING,
            device_id=device_id,
        )

    async def poll_qr_login(
        self, ticket: str, device_id: str, timeout: float | None = None
    ) -> QRLoginSession:
        timeout = timeout or self._qr_timeout
        interval = 2.0
        elapsed = 0.0
        client = genshin.Client(region=self._region, device_id=device_id)

        while elapsed < timeout:
            try:
                status, cookies = await client._check_qrcode(ticket)
            except genshin.GenshinException as exc:
                qr_status = QRLoginStatus.EXPIRED if exc.retcode == -106 else QRLoginStatus.CANCELED
                _logger.info("qr poll completed with retcode=%s -> %s", exc.retcode, qr_status.value)
                return QRLoginSession(
                    ticket=ticket,
                    qr_url="",
                    qr_image=b"",
                    status=qr_status,
                )
            except ValueError:
                _logger.info("qr poll: received unknown status -> CANCELED")
                return QRLoginSession(
                    ticket=ticket,
                    qr_url="",
                    qr_image=b"",
                    status=QRLoginStatus.CANCELED,
                )

            if status is QRCodeStatus.CONFIRMED:
                dict_cookies = {key: morsel.value for key, morsel in cookies.items()}
                return QRLoginSession(
                    ticket=ticket,
                    qr_url="",
                    qr_image=b"",
                    status=QRLoginStatus.CONFIRMED,
                    cookies=dict_cookies or None,
                )

            if status is QRCodeStatus.SCANNED:
                _logger.info("qr code scanned: ticket=%s", ticket)

            await asyncio.sleep(interval)
            elapsed += interval

        return QRLoginSession(
            ticket=ticket,
            qr_url="",
            qr_image=b"",
            status=QRLoginStatus.EXPIRED,
        )

    async def is_bound(self, user_id: str) -> bool:
        raw = await self._storage.get(_NS_HOYOLAB, user_id)
        return raw is not None

    async def _load_session(self, user_id: str) -> _SessionData | None:
        raw = await self._storage.get(_NS_HOYOLAB, user_id)
        if raw is None:
            return None
        cookies = raw.get("cookies")
        uid = raw.get("uid")
        device_id = raw.get("device_id")
        device_fp = raw.get("device_fp")
        if not cookies:
            return None
        if not uid:
            _logger.warning("hoyolab session missing uid: user=%s", user_id)
            return None
        if not device_id:
            _logger.warning("hoyolab session missing device_id: user=%s", user_id)
        return {"cookies": cookies, "uid": uid, "device_id": device_id, "device_fp": device_fp}

    async def _ensure_session(self, user_id: str) -> _SessionData:
        session = await self._load_session(user_id)
        if session is None:
            raise NotBoundError("请先使用 /hoyobind 绑定米游社账号")
        return session

    async def _resolve_uid(self, cookies: dict[str, str], *, device_id: str | None = None) -> str | None:
        client = genshin.Client(region=self._region, device_id=device_id)
        client.set_cookies(cookies)
        try:
            accounts = await client.get_game_accounts()
            for account in accounts:
                if account.game == genshin.Game.GENSHIN:
                    return str(account.uid)
            return None
        except Exception as exc:
            _logger.warning("failed to resolve uid: %s", exc, exc_info=True)
            return None

    async def bind(self, user_id: str, cookies: dict[str, str]) -> None:
        device_id = _generate_device_id()
        uid = await self._resolve_uid(cookies, device_id=device_id)
        device_fp: str | None = None
        try:
            client = genshin.Client(region=self._region, device_id=device_id)
            client.set_cookies(cookies)
            device_fp = await client.generate_fp(
                device_id=device_id,
                device_board="Xiaomi",
                oaid="".join(random.choices(string.ascii_lowercase + string.digits, k=16)),
            )
        except Exception as exc:
            _logger.warning("failed to generate device fingerprint: %s", exc)

        data: _SessionData = {
            "cookies": cookies,
            "uid": uid,
            "device_id": device_id,
            "device_fp": device_fp,
        }
        await self._storage.set(_NS_HOYOLAB, user_id, data)

    async def unbind(self, user_id: str) -> None:
        await self._storage.delete(_NS_HOYOLAB, user_id)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _prepare_client(self, session: _SessionData) -> genshin.Client:
        if self._client is None:
            self._client = genshin.Client(region=self._region, device_id=session.get("device_id"))
            self._client.device_fp = session.get("device_fp")
            self._client.custom_headers = {
                "User-Agent": _USER_AGENT,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "x-rpc-app_version": "2.102.0",
            }
        self._client.set_cookies(session["cookies"])
        return self._client

    # --- notes ---

    async def get_notes(self, user_id: str) -> NotesResult:
        try:
            session = await self._ensure_session(user_id)
            client = self._prepare_client(session)
            raw = await client.get_notes(uid=int(session["uid"]) if session.get("uid") else None)
            return NotesResult(
                    data=NotesData(
                        current_resin=raw.current_resin,
                        max_resin=raw.max_resin,
                        resin_recovery_time=raw.remaining_resin_recovery_time or "",
                        current_expeditions=len(raw.expeditions),
                        max_expeditions=raw.max_expeditions,
                        current_daily_task=raw.completed_commissions,
                        max_daily_task=raw.max_commissions,
                    )
                )
        except NotBoundError:
            raise
        except genshin.GenshinException as exc:
            return NotesResult(error=str(exc))
        except Exception as exc:
            _logger.exception("unexpected error in get_notes: user=%s", user_id)
            return NotesResult(error=f"内部错误: {exc}")

    # --- sign ---

    async def daily_sign(self, user_id: str) -> SignResult:
        try:
            session = await self._ensure_session(user_id)
            client = self._prepare_client(session)
            info = await client.get_reward_info(game=genshin.Game.GENSHIN)
            if info.signed_in:
                return SignResult(
                    data=CheckInResult(success=True, today_signed=True, message="今日已签到")
                )

            await client.claim_daily_reward(game=genshin.Game.GENSHIN, reward=False)
            return SignResult(data=CheckInResult(success=True, message="签到成功"))
        except NotBoundError:
            raise
        except genshin.AlreadyClaimed:
            return SignResult(
                data=CheckInResult(success=True, today_signed=True, message="今日已签到")
            )
        except genshin.GenshinException as exc:
            return SignResult(error=str(exc))
        except Exception as exc:
            _logger.exception("unexpected error in daily_sign: user=%s", user_id)
            return SignResult(error=f"内部错误: {exc}")

    # --- battle chronicle ---

    async def get_battle_chronicle(
        self, user_id: str, uid: str | None = None
    ) -> ChronicleResult:
        try:
            session = await self._ensure_session(user_id)
            resolved_uid = uid or session.get("uid")
            client = self._prepare_client(session)
            raw = await client.get_genshin_user(uid=int(resolved_uid) if resolved_uid else None)
            return ChronicleResult(
                data=ChronicleData(
                    uid=str(raw.info.uid),
                    region=self._region_str,
                )
            )
        except NotBoundError:
            raise
        except genshin.GeetestError:
            return ChronicleResult(error="请求被米游社风控拦截，请稍后再试。持续出现的话，尝试在米游社 APP 中正常使用几天可以降低风控等级。")
        except genshin.GenshinException as exc:
            return ChronicleResult(error=str(exc))
        except Exception as exc:
            _logger.exception("unexpected error in get_battle_chronicle: user=%s", user_id)
            return ChronicleResult(error=f"内部错误: {exc}")
