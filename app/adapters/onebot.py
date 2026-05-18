from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response

from app.event_model import Mention, MessageSender, NormalizedEvent, ReplyTarget, Scene
from app.router import Router

_logger = logging.getLogger(__name__)

_CQ_RE = re.compile(r"\[CQ:[^\]]+\]")
_CQ_AT_RE = re.compile(r"\[CQ:at,qq=(\d+)\]")
_CQ_REPLY_RE = re.compile(r"\[CQ:reply,id=(-?\d+)\]")


def _strip_cq_codes(text: str) -> str:
    return _CQ_RE.sub("", text).strip()


def _parse_mentions(raw_text: str) -> tuple[Mention, ...]:
    return tuple(Mention(user_id=m.group(1)) for m in _CQ_AT_RE.finditer(raw_text))


def _parse_reply_to(raw_text: str) -> str | None:
    m = _CQ_REPLY_RE.search(raw_text)
    return m.group(1) if m else None


def _parse_event(data: dict[str, Any]) -> NormalizedEvent | None:
    post_type = data.get("post_type")
    if post_type != "message":
        return None

    message_type = data.get("message_type")
    if message_type == "group":
        scene = Scene.GROUP
        chat_id = str(data.get("group_id", ""))
    elif message_type == "private":
        scene = Scene.PRIVATE
        chat_id = str(data.get("user_id", ""))
    else:
        return None

    user_id = str(data.get("user_id", ""))
    message_id = str(data.get("message_id", ""))
    raw_text = str(data.get("raw_message") or data.get("message") or "")
    text = _strip_cq_codes(raw_text)

    if not text:
        return None

    mentions = _parse_mentions(raw_text)
    reply_to = _parse_reply_to(raw_text)

    return NormalizedEvent(
        platform="qq",
        adapter="onebot",
        scene=scene,
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        text=text,
        mentions=mentions,
        reply_to=reply_to,
    )


class OneBotMessageSender:
    def __init__(self, api_base: str) -> None:
        self._api_base = api_base.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    @staticmethod
    def _build_payload(target: ReplyTarget, text: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": text}
        if target.scene == Scene.GROUP:
            payload["message_type"] = "group"
            payload["group_id"] = int(target.chat_id)
        else:
            payload["message_type"] = "private"
            payload["user_id"] = int(target.chat_id)
        return payload

    async def _post_with_retry(self, endpoint: str, payload: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(f"{self._api_base}{endpoint}", json=payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = 2 ** attempt
                    _logger.warning("%s attempt %d failed: %s, retrying in %ds", endpoint, attempt + 1, exc, wait)
                    await asyncio.sleep(wait)
        _logger.error("%s failed after %d attempts: %s", endpoint, max_retries + 1, last_exc)
        raise last_exc  # type: ignore[misc]

    async def send_text(self, target: ReplyTarget, text: str) -> str:
        payload = self._build_payload(target, text)
        data = await self._post_with_retry("/send_msg", payload)
        if data.get("retcode") != 0:
            _logger.warning("send_msg retcode=%s: %s", data.get("retcode"), data.get("msg", ""))
        return str(data.get("data", {}).get("message_id", ""))

    async def recall(self, message_id: str) -> bool:
        try:
            data = await self._post_with_retry("/delete_msg", {"message_id": message_id}, max_retries=1)
            return data.get("retcode") == 0
        except Exception:
            _logger.warning("recall failed for message_id=%s", message_id, exc_info=True)
            return False

    async def send_reply(self, event: NormalizedEvent, text: str) -> str:
        target = ReplyTarget(
            scene=event.scene,
            chat_id=event.chat_id,
            user_id=event.user_id,
        )
        return await self.send_text(target, text)

    async def send_image(self, target: ReplyTarget, image_data: bytes) -> str:
        b64 = base64.b64encode(image_data).decode()
        return await self.send_text(target, f"[CQ:image,file=base64://{b64}]")

    async def send_reply_image(self, event: NormalizedEvent, image_data: bytes) -> str:
        target = ReplyTarget(
            scene=event.scene,
            chat_id=event.chat_id,
            user_id=event.user_id,
        )
        return await self.send_image(target, image_data)

    async def close(self) -> None:
        await self._client.aclose()


class OneBotAdapter:
    def __init__(
        self,
        router: Router,
        webhook_host: str,
        webhook_port: int,
        webhook_path: str,
        api_base: str,
    ) -> None:
        self._router = router
        self._webhook_host = webhook_host
        self._webhook_port = webhook_port
        self._webhook_path = webhook_path
        self._sender = OneBotMessageSender(api_base)
        self._app = self._build_app()
        self._runner: Any = None

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post(self._webhook_path)
        async def webhook(request: Request) -> Response:
            try:
                body = await request.json()
            except Exception:
                return Response(status_code=400)

            event = _parse_event(body)
            if event is None:
                return Response(status_code=200)

            _logger.info("onebot event: scene=%s chat=%s user=%s text=%s", event.scene, event.chat_id, event.user_id, event.text)
            asyncio.ensure_future(self._dispatch(event))
            return Response(status_code=200)

        return app

    async def _dispatch(self, event: NormalizedEvent) -> None:
        try:
            result = await self._router.dispatch(event, self._sender)
        except Exception:
            _logger.exception("dispatch error for onebot event")
            return

        if result and result.text:
            try:
                await self._sender.send_reply(event, result.text)
            except Exception:
                _logger.exception("failed to send reply for onebot event")

    async def start(self) -> None:
        from app.http import UvicornServerRunner

        self._runner = UvicornServerRunner(
            self._app,
            host=self._webhook_host,
            port=self._webhook_port,
            log_level="info",
            shutdown_timeout=5.0,
        )
        await self._runner.start()
        _logger.info("onebot adapter started on %s:%s", self._webhook_host, self._webhook_port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.stop()
        await self._sender.close()
        _logger.info("onebot adapter stopped")
