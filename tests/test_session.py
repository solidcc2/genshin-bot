from __future__ import annotations

import pytest

from app.session import MessageRecord, Session, SessionManager
from app.storage.memory import MemoryStorage


@pytest.fixture
def manager():
    storage = MemoryStorage()
    return SessionManager(storage)


class TestMessageRecord:
    def test_default_timestamp(self) -> None:
        rec = MessageRecord(role="user", text="hello")
        assert rec.role == "user"
        assert rec.text == "hello"
        assert rec.timestamp is not None


class TestSession:
    def test_default_values(self) -> None:
        s = Session(chat_id="chat_001")
        assert s.chat_id == "chat_001"
        assert s.messages == []
        assert s.state == {}
        assert s.created_at is not None
        assert s.updated_at is not None


class TestSessionManager:
    @pytest.mark.anyio
    async def test_get_or_create_new(self, manager) -> None:
        session = await manager.get_or_create("new_chat")
        assert session.chat_id == "new_chat"
        assert session.messages == []
        assert session.state == {}

    @pytest.mark.anyio
    async def test_get_or_create_existing(self, manager) -> None:
        await manager.add_message("chat_001", "user", "hello")
        session = await manager.get_or_create("chat_001")
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].text == "hello"

    @pytest.mark.anyio
    async def test_add_message_appends(self, manager) -> None:
        await manager.add_message("chat_001", "user", "first")
        await manager.add_message("chat_001", "assistant", "second")

        session = await manager.get_or_create("chat_001")
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].text == "first"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].text == "second"

    @pytest.mark.anyio
    async def test_add_message_updates_timestamp(self, manager) -> None:
        session1 = await manager.get_or_create("chat_001")
        old_updated = session1.updated_at

        await manager.add_message("chat_001", "user", "hello")
        session2 = await manager.get_or_create("chat_001")
        assert session2.updated_at >= old_updated

    @pytest.mark.anyio
    async def test_max_history_cap(self, manager) -> None:
        manager._max_history = 3
        for i in range(5):
            await manager.add_message("chat_001", "user", f"msg_{i}")

        session = await manager.get_or_create("chat_001")
        assert len(session.messages) == 3
        assert session.messages[0].text == "msg_2"
        assert session.messages[-1].text == "msg_4"

    @pytest.mark.anyio
    async def test_set_and_get_state(self, manager) -> None:
        await manager.set_state("chat_001", "scene", "combat")
        val = await manager.get_state("chat_001", "scene")
        assert val == "combat"

    @pytest.mark.anyio
    async def test_get_state_missing_key(self, manager) -> None:
        val = await manager.get_state("chat_001", "nonexistent")
        assert val is None

    @pytest.mark.anyio
    async def test_state_isolated_per_chat(self, manager) -> None:
        await manager.set_state("chat_001", "step", 1)
        await manager.set_state("chat_002", "step", 99)

        assert await manager.get_state("chat_001", "step") == 1
        assert await manager.get_state("chat_002", "step") == 99

    @pytest.mark.anyio
    async def test_messages_isolated_per_chat(self, manager) -> None:
        await manager.add_message("chat_001", "user", "hello")
        await manager.add_message("chat_002", "user", "world")

        s1 = await manager.get_or_create("chat_001")
        s2 = await manager.get_or_create("chat_002")
        assert len(s1.messages) == 1
        assert s1.messages[0].text == "hello"
        assert len(s2.messages) == 1
        assert s2.messages[0].text == "world"

    @pytest.mark.anyio
    async def test_state_preserved_with_messages(self, manager) -> None:
        await manager.set_state("chat_001", "count", 5)
        await manager.add_message("chat_001", "user", "go")
        session = await manager.get_or_create("chat_001")
        assert session.state.get("count") == 5
        assert len(session.messages) == 1

    @pytest.mark.anyio
    async def test_multiple_state_keys(self, manager) -> None:
        await manager.set_state("chat_001", "a", 1)
        await manager.set_state("chat_001", "b", 2)
        assert await manager.get_state("chat_001", "a") == 1
        assert await manager.get_state("chat_001", "b") == 2
