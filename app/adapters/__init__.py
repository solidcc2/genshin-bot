from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.event_model import NormalizedEvent, ReplyTarget, Scene
from app.plugin import PluginResult
from app.router import Router


@dataclass
class CLIMessageSender:
    reply_target: ReplyTarget = field(
        default_factory=lambda: ReplyTarget(scene=Scene.PRIVATE, chat_id="cli")
    )

    async def send_text(self, target: ReplyTarget, text: str) -> str:
        print(text, file=sys.stdout)
        return f"cli_{datetime.now(timezone.utc).timestamp()}"

    async def send_reply(self, event: NormalizedEvent, text: str) -> str:
        return await self.send_text(self.reply_target, text)

    def display_result(self, result: PluginResult) -> None:
        if result.text:
            print(result.text, file=sys.stdout)


class CLIAdapter:
    """Reads lines from stdin, dispatches through router, prints results."""

    def __init__(self, router: Router) -> None:
        self._router = router
        self._sender = CLIMessageSender()
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._print_banner()

        while self._running:
            sys.stdout.write("> ")
            sys.stdout.flush()
            try:
                line = await asyncio.to_thread(sys.stdin.readline)
            except (KeyboardInterrupt, EOFError):
                break

            if not line:
                break  # EOF

            text = line.rstrip("\n\r")
            if not text:
                continue

            if text.strip() == "/quit":
                break

            event = NormalizedEvent(
                platform="cli",
                adapter="stdin",
                scene=Scene.PRIVATE,
                chat_id="cli",
                user_id="cli",
                message_id=f"cli_{datetime.now(timezone.utc).timestamp()}",
                text=text,
            )

            try:
                result = await self._router.dispatch(event, self._sender)
                self._sender.display_result(result)
            except Exception as exc:
                print(f"错误: {exc}", file=sys.stderr)

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _print_banner() -> None:
        print("CLI adapter started. Type /help for commands, /quit to exit.", file=sys.stdout)
        print(file=sys.stdout)
