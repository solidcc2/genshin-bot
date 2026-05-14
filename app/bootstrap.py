from __future__ import annotations

import asyncio
import argparse
from collections.abc import Callable
import signal
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from app.config import ConfigLoader
from app.errors import ApplicationStateError, BootstrapError
from app.http import HealthService
from app.logging import configure_logging
from app.runtime import AppContext


class Application:
    def __init__(self, context: AppContext, health_service: HealthService) -> None:
        self.context = context
        self._health_service = health_service

    async def start(self) -> None:
        if self.context.runtime.status == "running":
            raise ApplicationStateError("Application is already running")

        host, port = await self._health_service.start()
        self.context.runtime.mark_started(host=host, port=port)
        self.context.logger.info("application started")

    async def stop(self) -> None:
        if self.context.runtime.status not in {"running", "created"}:
            raise ApplicationStateError("Application is not in a stoppable state")

        await self._health_service.stop()
        self.context.runtime.mark_stopped()
        self.context.logger.info("application stopped")


def build_application(
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    health_runner_factory: Callable[[FastAPI, Any], Any] | None = None,
) -> Application:
    config = ConfigLoader.load(config_path=config_path, environ=environ)
    logger = configure_logging(config.log_level)
    context = AppContext(config=config, logger=logger)
    health_service = HealthService(context, runner_factory=health_runner_factory)
    context.services.register("health_service", health_service)
    return Application(context=context, health_service=health_service)


async def async_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the QQ AI bot runtime skeleton.")
    parser.add_argument("--config", default=None, help="Path to JSON config file.")
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

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))
