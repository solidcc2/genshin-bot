from __future__ import annotations

import asyncio
import argparse
from collections.abc import Callable
import signal
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from app.adapters import CLIAdapter
from app.chat_log import ChatLogStore
from app.config import ConfigLoader
from app.dedup import MessageDedupStore
from app.errors import ApplicationStateError, BootstrapError
from app.http import HealthService
from app.logging import configure_logging
from app.plugins.echo import EchoPlugin
from app.plugins.help import HelpPlugin
from app.plugins.null import NullPlugin
from app.plugins.ping import PingPlugin
from app.rate_limit import RateLimiter
from app.router import Router
from app.runtime import AppContext
from app.session import SessionManager
from app.storage import create_storage


class Application:
    def __init__(self, context: AppContext, health_service: HealthService) -> None:
        self.context = context
        self._health_service = health_service

    async def start(self) -> None:
        if self.context.runtime.status == "running":
            raise ApplicationStateError("Application is already running")

        host, port = await self._health_service.start()

        if self.context.services.has("onebot_adapter"):
            await self.context.services.get("onebot_adapter").start()

        self.context.runtime.mark_started(host=host, port=port)
        self.context.logger.info("application started")

    async def stop(self) -> None:
        if self.context.runtime.status not in {"running", "created"}:
            raise ApplicationStateError("Application is not in a stoppable state")

        if self.context.services.has("onebot_adapter"):
            await self.context.services.get("onebot_adapter").stop()

        if self.context.services.has("llm_provider"):
            await self.context.services.get("llm_provider").close()
        if self.context.services.has("hoyolab_provider"):
            await self.context.services.get("hoyolab_provider").close()

        await self._health_service.stop()

        if self.context.storage is not None:
            await self.context.storage.close()
        if self.context.chat_log is not None:
            await self.context.chat_log.close()

        self.context.runtime.mark_stopped()
        self.context.logger.info("application stopped")


def build_application(
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    health_runner_factory: Callable[..., Any] | None = None,
) -> Application:
    config = ConfigLoader.load(config_path=config_path, environ=environ)
    logger = configure_logging(config.log_level)
    context = AppContext(config=config, logger=logger)

    # Storage first — Router depends on dedup from storage
    _init_storage(context)

    context.router = Router(
        context.plugins,
        dedup=context.dedup,
        chat_log=context.chat_log,
        bot_user_id=context.config.llm.bot_qq_id,
    )
    _register_core_plugins(context)

    # OneBot adapter (runs if enabled in config)
    if config.onebot.enabled:
        from app.adapters.onebot import OneBotAdapter

        onebot = OneBotAdapter(
            router=context.router,
            webhook_host=config.onebot.webhook_host,
            webhook_port=config.onebot.webhook_port,
            webhook_path=config.onebot.webhook_path,
            api_base=config.onebot.api_base,
        )
        context.services.register("onebot_adapter", onebot)

    health_service = HealthService(context, runner_factory=health_runner_factory)
    context.services.register("health_service", health_service)
    return Application(context=context, health_service=health_service)


def _init_storage(context: AppContext) -> None:
    storage = create_storage(context.config.storage)
    context.storage = storage
    context.session_manager = SessionManager(storage)
    context.rate_limiter = RateLimiter(storage)
    context.dedup = MessageDedupStore(storage)
    context.chat_log = ChatLogStore(
        context.config.storage.db_path,
        max_count=context.config.storage.chat_log_max,
        min_count=context.config.storage.chat_log_min,
    )


def _register_core_plugins(context: AppContext) -> None:
    echo = EchoPlugin()
    ping = PingPlugin()
    help_ = HelpPlugin(context.plugins)

    for plugin in (echo, ping, help_):
        context.router.register(plugin)

    _register_chat_log_admin_plugin(context)
    _register_llm_refresh_plugin(context)
    _register_genshin_plugins(context)
    _register_chat_plugin(context)
    _register_staticdata_plugins(context)

    # NullPlugin must be registered last — its match() always returns True
    context.router.register(NullPlugin())


def _register_chat_log_admin_plugin(context: AppContext) -> None:
    from app.plugins.chat_log_admin import ChatLogClearPlugin

    if context.chat_log is not None:
        context.router.register(ChatLogClearPlugin(context.chat_log))


def _register_llm_refresh_plugin(context: AppContext) -> None:
    from app.plugins.llm_refresh import LLMRefreshEnvPlugin

    if context.session_manager is not None:
        context.router.register(LLMRefreshEnvPlugin(context.session_manager))


def _register_chat_plugin(context: AppContext) -> None:
    llm_config = context.config.llm
    if not llm_config.enabled:
        return
    if not llm_config.api_key:
        context.logger.warning("llm enabled but api_key not set, chat plugin skipped")
        return

    from app.llm import ContextBuilder, DeepSeekProvider, ModelRouter
    from app.plugins.chat import ChatPlugin
    from app.signals import create_evaluator

    assert context.session_manager is not None

    provider = DeepSeekProvider(
        api_key=llm_config.api_key,
        endpoint=llm_config.endpoint,
        timeout=llm_config.timeout,
        max_retries=llm_config.max_retries,
    )
    model_router = ModelRouter(
        default_model=llm_config.default_model,
        upgrade_model=llm_config.upgrade_model,
    )
    context_builder = ContextBuilder(
        persona=llm_config.system_prompt,
        plugin_registry=context.plugins,
        chat_log=context.chat_log,
        context_limit=llm_config.context_messages_limit,
        bot_user_id=llm_config.bot_qq_id,
    )

    signal_evaluator = create_evaluator(
        mode=llm_config.response_mode,
        bot_qq_id=llm_config.bot_qq_id,
        bot_name=llm_config.bot_name,
        threshold=llm_config.threshold,
        signals=llm_config.signals,
    )

    from app.llm.tracker import TokenUsageTracker

    tracker = TokenUsageTracker(
        storage=context.storage,
        max_per_day=llm_config.max_tokens_per_day,
        max_total=llm_config.max_tokens_total,
    )

    context.router.register(ChatPlugin(
        provider=provider,
        session_manager=context.session_manager,
        context_builder=context_builder,
        router=model_router,
        tracker=tracker,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        signal_evaluator=signal_evaluator,
        max_response_delay=llm_config.max_response_delay,
    ))
    context.services.register("llm_provider", provider)


def _register_genshin_plugins(context: AppContext) -> None:
    from app.plugins.genshin import register as register_genshin

    provider = register_genshin(
        router=context.router,
        storage=context.storage,
        hoyolab_config=context.config.hoyolab,
    )
    if provider is not None:
        context.services.register("hoyolab_provider", provider)


def _register_staticdata_plugins(context: AppContext) -> None:
    from pathlib import Path

    from app.plugins.staticdata import DataPlugin
    from app.providers.staticdata import StaticDataProvider

    data_dir = Path(__file__).resolve().parent / "data"
    provider = StaticDataProvider(data_dir)
    context.router.register(DataPlugin(provider))


async def async_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the QQ AI bot runtime skeleton.")
    parser.add_argument("--config", default=None, help="Path to JSON config file.")
    parser.add_argument(
        "--cli", action="store_true", help="Start CLI adapter for interactive input."
    )
    args = parser.parse_args(argv)

    try:
        application = build_application(config_path=args.config)
        await application.start()
    except BootstrapError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - final safety net
        print(f"unexpected startup failure: {exc}", file=sys.stderr)
        return 1

    stop_event = asyncio.Event()

    if args.cli:
        cli = CLIAdapter(application.context.router)
        cli_task = asyncio.create_task(cli.run())

        def _on_cli_done(task: asyncio.Task[None]) -> None:
            if task.cancelled():
                stop_event.set()
                return
            exc = task.exception()
            if exc:
                print(f"CLI adapter error: {exc}", file=sys.stderr)
            stop_event.set()

        cli_task.add_done_callback(_on_cli_done)

    def _handle_signal(_signum: int, _frame: object) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            signal.signal(sig, _handle_signal)

    try:
        await stop_event.wait()
    finally:
        await application.stop()
        if args.cli and cli_task and not cli_task.done():
            cli_task.cancel()
            try:
                await cli_task
            except asyncio.CancelledError:
                pass

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))
