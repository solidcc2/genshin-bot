import pytest

from app.event_model import NormalizedEvent, Scene
from app.llm.context import ContextBuilder
from app.llm.models import LLMMessage
from app.llm.routing import ModelRouter
from app.plugin import PluginContext, PluginRegistry
from app.plugins.chat import ChatPlugin
from app.session import Session, SessionManager
from app.storage.memory import MemoryStorage
from tests.conftest import FakeModelProvider, make_event, FakeSender


def _make_chat_plugin(response: str | None = None) -> ChatPlugin:
    provider = FakeModelProvider(response=response)
    storage = MemoryStorage()
    session_manager = SessionManager(storage)
    plugins = PluginRegistry()
    router = ModelRouter()
    context_builder = ContextBuilder(persona="你是测试助手。", plugin_registry=plugins)
    return ChatPlugin(
        provider=provider,
        session_manager=session_manager,
        context_builder=context_builder,
        router=router,
    )


class TestChatPluginMatch:
    def test_matches_non_command(self) -> None:
        plugin = _make_chat_plugin()
        event = make_event("你好")
        assert plugin.match(event) is True

    def test_does_not_match_slash_command(self) -> None:
        plugin = _make_chat_plugin()
        event = make_event("/help")
        assert plugin.match(event) is False

    def test_does_not_match_unknown_slash(self) -> None:
        plugin = _make_chat_plugin()
        event = make_event("/unknowncommand")
        assert plugin.match(event) is False

    def test_matches_non_command_with_spaces(self) -> None:
        plugin = _make_chat_plugin()
        event = make_event("  今天天气怎么样  ")
        assert plugin.match(event) is True


@pytest.mark.anyio
class TestChatPluginHandle:
    async def test_returns_llm_response(self) -> None:
        plugin = _make_chat_plugin("测试回复")
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert result.text == "测试回复"

    async def test_includes_context_layers(self) -> None:
        plugin = _make_chat_plugin()
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        await plugin.handle(ctx)
        assert plugin._provider.last_messages is not None
        roles = [m.role for m in plugin._provider.last_messages]
        assert "system" in roles
        assert "user" in roles
        # Should have system persona + system skills + user message
        assert len(plugin._provider.last_messages) >= 2

    async def test_saves_to_session_on_success(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("OK")
        context_builder = ContextBuilder(persona="test", plugin_registry=plugins)
        router = ModelRouter()
        plugin = ChatPlugin(
            provider=provider,
            session_manager=session_manager,
            context_builder=context_builder,
            router=router,
        )
        event = make_event("hello")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        await plugin.handle(ctx)

        session = await session_manager.get_or_create(event.chat_id)
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].text == "hello"
        assert session.messages[1].role == "assistant"

    async def test_does_not_save_on_failure(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("OK")

        async def failing_generate(messages, model=None, **kwargs):
            from app.errors import LLMAPIError
            raise LLMAPIError("API failure")

        provider.generate = failing_generate  # type: ignore[assignment]
        context_builder = ContextBuilder(persona="test", plugin_registry=plugins)
        router = ModelRouter()
        plugin = ChatPlugin(
            provider=provider,
            session_manager=session_manager,
            context_builder=context_builder,
            router=router,
        )
        event = make_event("hello")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert "抱歉" in (result.text or "")

        session = await session_manager.get_or_create(event.chat_id)
        assert len(session.messages) == 0

    async def test_session_isolation(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("reply")
        context_builder = ContextBuilder(persona="test", plugin_registry=plugins)
        router = ModelRouter()
        plugin = ChatPlugin(
            provider=provider,
            session_manager=session_manager,
            context_builder=context_builder,
            router=router,
        )
        sender = FakeSender()

        ev1 = make_event("msg1", chat_id="chat_a")
        await plugin.handle(PluginContext(event=ev1, sender=sender))
        ev2 = make_event("msg2", chat_id="chat_b")
        await plugin.handle(PluginContext(event=ev2, sender=sender))

        sa = await session_manager.get_or_create("chat_a")
        sb = await session_manager.get_or_create("chat_b")
        assert len(sa.messages) == 2
        assert len(sb.messages) == 2
        assert sa.messages[0].text == "msg1"
        assert sb.messages[0].text == "msg2"
