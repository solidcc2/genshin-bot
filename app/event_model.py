from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol


class Scene(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    GUILD = "guild"
    CHANNEL = "channel"


@dataclass(frozen=True)
class Mention:
    user_id: str
    display_name: str = ""


@dataclass(frozen=True)
class NormalizedEvent:
    platform: str
    adapter: str
    scene: Scene
    chat_id: str
    user_id: str
    message_id: str
    text: str
    mentions: tuple[Mention, ...] = ()
    reply_to: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ReplyTarget:
    scene: Scene
    chat_id: str
    user_id: str | None = None


class MessageSender(Protocol):
    async def send_text(self, target: ReplyTarget, text: str) -> str: ...
    async def send_reply(
        self, event: NormalizedEvent, text: str
    ) -> str: ...

    async def send_image(self, target: ReplyTarget, image_data: bytes) -> str:
        """Send an image. Default fallback sends byte count as text."""
        return await self.send_text(target, f"[图片 {len(image_data)} 字节]")

    async def send_reply_image(self, event: NormalizedEvent, image_data: bytes) -> str:
        """Send an image as reply."""
        target = ReplyTarget(scene=event.scene, chat_id=event.chat_id, user_id=event.user_id)
        return await self.send_image(target, image_data)

    async def recall(self, message_id: str) -> bool:
        """Recall/delete a previously sent message. Default no-op."""
        return False
