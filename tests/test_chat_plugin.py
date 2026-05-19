import pytest

from app.event_model import NormalizedEvent, Scene
from app.llm.context import ContextBuilder
from app.llm.models import LLMMessage
from app.llm.routing import ModelRouter
from app.llm.tracker import TokenUsageTracker
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


class TestParseResponse:
    def test_formatted_reply(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("是, +0s, 今天天气不错")
        assert reply is True
        assert delay == 0
        assert content == "今天天气不错"

    def test_formatted_reply_with_delay(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("是, +5s, 稍等")
        assert reply is True
        assert delay == 5
        assert content == "稍等"

    def test_bare_no_returns_no_reply(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("否")
        assert reply is False
        assert delay == 0
        assert content == ""

    def test_formatted_no_returns_no_reply(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("否, +0s, ")
        assert reply is False
        assert delay == 0
        assert content == ""

    def test_sends_plain_text_without_format(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("普通句子没有格式")
        assert reply is True
        assert delay == 0
        assert content == "普通句子没有格式"

    def test_empty_text_returns_no_reply(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("")
        assert reply is False
        assert delay == 0
        assert content == ""

    def test_chinese_comma(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("是，+0s，今天天气不错")
        assert reply is True
        assert delay == 0
        assert content == "今天天气不错"

    def test_chinese_comma_with_delay(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("是，+5s，稍等")
        assert reply is True
        assert delay == 5
        assert content == "稍等"

    def test_chinese_comma_no_reply(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("否，+0s，")
        assert reply is False
        assert delay == 0
        assert content == ""

    def test_relaxed_format_missing_prefix(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("+0s, 直接回复")
        assert reply is True
        assert delay == 0
        assert content == "直接回复"

    def test_relaxed_format_with_delay(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("+5s, 稍等回复")
        assert reply is True
        assert delay == 5
        assert content == "稍等回复"

    def test_relaxed_format_chinese_comma(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("+3s，内容")
        assert reply is True
        assert delay == 3
        assert content == "内容"

    def test_bare_yes_sends_text(self) -> None:
        from app.plugins.chat import _parse_response
        reply, delay, content = _parse_response("是")
        assert reply is True
        assert delay == 0
        assert content == "是"


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
        plugin = _make_chat_plugin("是, +0s, 测试回复")
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

    async def test_returns_response_on_success(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("是, +0s, OK")
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
        assert result.text == "OK"

    async def test_returns_error_message_on_failure(self) -> None:
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

    async def test_does_not_send_bare_no(self) -> None:
        plugin = _make_chat_plugin("否")
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert result.text is None

    async def test_sends_plain_text_without_format(self) -> None:
        plugin = _make_chat_plugin("一些随机的非格式文本")
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert result.text == "一些随机的非格式文本"

    async def test_relaxed_format_missing_prefix(self) -> None:
        plugin = _make_chat_plugin("+0s, 直接回复")
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert result.text == "直接回复"

    async def test_relaxed_format_chinese_comma(self) -> None:
        plugin = _make_chat_plugin("+3s，稍等回复")
        event = make_event("你好")
        sender = FakeSender()
        ctx = PluginContext(event=event, sender=sender)
        result = await plugin.handle(ctx)
        assert result.text == "稍等回复"

    async def test_chat_isolation(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("是, +0s, reply")
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
        assert sa.chat_id == "chat_a"
        assert sb.chat_id == "chat_b"

    async def test_returns_quota_message_when_tracker_blocks(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("OK")
        context_builder = ContextBuilder(persona="test", plugin_registry=plugins)
        router = ModelRouter()
        tracker = TokenUsageTracker(storage, max_per_day=10)
        await tracker.record(10)  # daily quota exhausted
        plugin = ChatPlugin(
            provider=provider,
            session_manager=session_manager,
            context_builder=context_builder,
            router=router,
            tracker=tracker,
        )
        event = make_event("hello")
        ctx = PluginContext(event=event, sender=FakeSender())
        result = await plugin.handle(ctx)

        assert "用尽" in (result.text or "")
        assert provider.call_count == 0  # LLM was NOT invoked

    async def test_records_tokens_after_success(self) -> None:
        storage = MemoryStorage()
        session_manager = SessionManager(storage)
        plugins = PluginRegistry()
        provider = FakeModelProvider("OK")
        context_builder = ContextBuilder(persona="test", plugin_registry=plugins)
        router = ModelRouter()
        tracker = TokenUsageTracker(storage, max_per_day=100)
        plugin = ChatPlugin(
            provider=provider,
            session_manager=session_manager,
            context_builder=context_builder,
            router=router,
            tracker=tracker,
        )
        event = make_event("hello")
        ctx = PluginContext(event=event, sender=FakeSender())
        await plugin.handle(ctx)

        daily = await tracker.daily_usage()
        assert daily > 0
