from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from app.config import AppConfig, ConfigLoader
from app.errors import ApplicationStateError, BootstrapError, ConfigError
from app.http import HealthService
from app.logging import configure_logging
from app.runtime import AppContext


class Application:
    def __init__(self, context: AppContext, health_service: HealthService) -> None:
        self.context = context
        self._health_service = health_service

    def start(self) -> None:
        if self.context.runtime.status == "running":
            raise ApplicationStateError("Application is already running")

        host, port = self._health_service.start()
        self.context.runtime.mark_started(host=host, port=port)
        self.context.logger.info("application started")

    def stop(self) -> None:
        if self.context.runtime.status not in {"running", "created"}:
            raise ApplicationStateError("Application is not in a stoppable state")

        self._health_service.stop()
        self.context.runtime.mark_stopped()
        self.context.logger.info("application stopped")


def build_application(
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Application:
    config = ConfigLoader.load(config_path=config_path, environ=environ)
    logger = configure_logging(config.log_level)
    context = AppContext(config=config, logger=logger)
    health_service = HealthService(context)
    context.services.register("health_service", health_service)
    return Application(context=context, health_service=health_service)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the QQ AI bot runtime skeleton.")
    parser.add_argument("--config", default=None, help="Path to JSON config file.")
    args = parser.parse_args(argv)

    try:
        application = build_application(config_path=args.config)
        application.start()
    except BootstrapError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - final safety net
        print(f"unexpected startup failure: {exc}", file=sys.stderr)
        return 1

    should_stop = False

    def _handle_signal(_signum: int, _frame: object) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while not should_stop:
            time.sleep(0.2)
    finally:
        application.stop()

    return 0
