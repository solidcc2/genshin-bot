from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.storage import StorageProvider


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


@dataclass
class MessageRecord:
    role: str
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Session:
    chat_id: str
    messages: list[MessageRecord] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_NS_SESSION = "session"


class SessionManager:
    def __init__(self, storage: StorageProvider, max_history: int = 50) -> None:
        self._storage = storage
        self._max_history = max_history

    async def get_or_create(self, chat_id: str) -> Session:
        data = await self._storage.get(_NS_SESSION, chat_id)
        if data is not None:
            return Session(
                chat_id=chat_id,
                messages=[
                    MessageRecord(
                        role=m["role"],
                        text=m["text"],
                        timestamp=_parse_timestamp(m["timestamp"]),
                    )
                    for m in data.get("messages", [])
                ],
                state=data.get("state", {}),
                created_at=_parse_timestamp(data["created_at"]),
                updated_at=_parse_timestamp(data["updated_at"]),
            )
        return Session(chat_id=chat_id)

    async def save(self, session: Session) -> None:
        session.updated_at = datetime.now(timezone.utc)
        data = {
            "messages": [
                {"role": m.role, "text": m.text, "timestamp": m.timestamp.isoformat()}
                for m in session.messages
            ],
            "state": session.state,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
        await self._storage.set(_NS_SESSION, session.chat_id, data)

    async def add_message(self, chat_id: str, role: str, text: str) -> None:
        session = await self.get_or_create(chat_id)
        session.messages.append(MessageRecord(role=role, text=text))
        if len(session.messages) > self._max_history:
            session.messages = session.messages[-self._max_history :]
        await self.save(session)

    async def set_state(self, chat_id: str, key: str, value: Any) -> None:
        session = await self.get_or_create(chat_id)
        session.state[key] = value
        await self.save(session)

    async def get_state(self, chat_id: str, key: str) -> Any | None:
        session = await self.get_or_create(chat_id)
        return session.state.get(key)
