import base64

import pytest

from app.adapters.onebot import OneBotMessageSender, _parse_event, _strip_cq_codes
from app.event_model import NormalizedEvent, ReplyTarget, Scene


class TestStripCQCodes:
    def test_no_cq_codes(self) -> None:
        assert _strip_cq_codes("hello world") == "hello world"

    def test_preserves_at_mention(self) -> None:
        raw = "[CQ:at,qq=123456] 你好"
        assert _strip_cq_codes(raw) == "@123456 你好"

    def test_strips_non_at_cq_codes(self) -> None:
        raw = "[CQ:at,qq=111] [CQ:face,id=123] 测试消息 [CQ:image,file=abc.jpg]"
        assert _strip_cq_codes(raw) == "@111 测试消息"

    def test_only_cq_codes_returns_at_only(self) -> None:
        assert _strip_cq_codes("[CQ:at,qq=1]") == "@1"

    def test_empty_string(self) -> None:
        assert _strip_cq_codes("") == ""


class TestParseEvent:
    def test_group_message(self) -> None:
        event = _parse_event(
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 123456,
                "user_id": 789012,
                "message_id": -123456789,
                "raw_message": "/help",
                "message": "/help",
            }
        )
        assert event is not None
        assert event.platform == "qq"
        assert event.adapter == "onebot"
        assert event.scene == Scene.GROUP
        assert event.chat_id == "123456"
        assert event.user_id == "789012"
        assert event.message_id == "-123456789"
        assert event.text == "/help"

    def test_private_message(self) -> None:
        event = _parse_event(
            {
                "post_type": "message",
                "message_type": "private",
                "user_id": 111222,
                "message_id": 888,
                "raw_message": "/ping",
            }
        )
        assert event is not None
        assert event.scene == Scene.PRIVATE
        assert event.chat_id == "111222"
        assert event.text == "/ping"

    def test_non_message_post_type(self) -> None:
        event = _parse_event(
            {
                "post_type": "notice",
                "notice_type": "group_increase",
                "group_id": 123,
                "user_id": 456,
            }
        )
        assert event is None

    def test_unknown_message_type(self) -> None:
        event = _parse_event(
            {
                "post_type": "message",
                "message_type": "guild",
                "guild_id": 1,
                "user_id": 2,
            }
        )
        assert event is None

    def test_empty_text_returns_none(self) -> None:
        event = _parse_event(
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 1,
                "user_id": 2,
                "message_id": 3,
                "message": "[CQ:image,file=pic.jpg]",
            }
        )
        assert event is None

    def test_strips_cq_codes_in_message_text(self) -> None:
        event = _parse_event(
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 1,
                "user_id": 2,
                "message_id": 3,
                "raw_message": "[CQ:at,qq=2] 签到",
            }
        )
        assert event is not None
        assert event.text == "@2 签到"


class TestOneBotMessageSender:
    def test_group_payload(self) -> None:
        target = ReplyTarget(scene=Scene.GROUP, chat_id="123", user_id="456")
        payload = OneBotMessageSender._build_payload(target, "hello")
        assert payload == {"message": "hello", "message_type": "group", "group_id": 123}

    def test_private_payload(self) -> None:
        target = ReplyTarget(scene=Scene.PRIVATE, chat_id="789", user_id="789")
        payload = OneBotMessageSender._build_payload(target, "world")
        assert payload == {"message": "world", "message_type": "private", "user_id": 789}

    def test_send_image_encodes_base64_in_message(self) -> None:
        sender = OneBotMessageSender("http://localhost:3000")
        image_data = b"test_image_bytes"
        expected = f"[CQ:image,file=base64://{base64.b64encode(image_data).decode()}]"
        target = ReplyTarget(scene=Scene.PRIVATE, chat_id="1", user_id="1")
        payload = sender._build_payload(target, expected)
        assert payload["message"] == expected

    def test_send_reply_image_derives_target_from_event(self) -> None:
        event = NormalizedEvent(
            platform="qq",
            adapter="onebot",
            scene=Scene.GROUP,
            chat_id="999",
            user_id="888",
            message_id="777",
            text="ignored",
        )
        sender = OneBotMessageSender("http://localhost:3000")
        target = ReplyTarget(scene=event.scene, chat_id=event.chat_id, user_id=event.user_id)
        payload = sender._build_payload(target, "[CQ:image,file=base64://ab12]")
        assert payload["message_type"] == "group"
        assert payload["group_id"] == 999
