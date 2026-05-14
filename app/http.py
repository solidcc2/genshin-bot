from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from app.config import AppConfig
from app.errors import HealthServiceError
from app.runtime import AppContext


class UvicornServerRunner:
    def __init__(self, app: FastAPI, config: AppConfig) -> None:
        self._app = app
        self._config = config
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> tuple[str, int]:
        uvicorn_config = uvicorn.Config(
            app=self._app,
            host=self._config.http.host,
            port=self._config.http.port,
            log_level=self._config.log_level.lower(),
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(uvicorn_config)
        self._server.install_signal_handlers = lambda: None
        self._task = asyncio.create_task(self._server.serve())

        for _ in range(500):
            if self._server.started:
                return self._resolve_bound_address()
            if self._task.done():
                await self._await_server_task()
                break
            await asyncio.sleep(0.01)

        raise HealthServiceError("timed out while starting health service")

    async def stop(self) -> None:
        if self._server is None:
            return

        self._server.should_exit = True
        if self._task is not None:
            await asyncio.wait_for(
                self._await_server_task(),
                timeout=self._config.http.shutdown_timeout,
            )
        self._task = None
        self._server = None

    async def _await_server_task(self) -> None:
        assert self._task is not None
        try:
            await self._task
        except OSError as exc:
            raise HealthServiceError(f"failed to start health service: {exc}") from exc
        except Exception as exc:
            raise HealthServiceError(f"health service failed unexpectedly: {exc}") from exc

    def _resolve_bound_address(self) -> tuple[str, int]:
        assert self._server is not None
        servers = getattr(self._server, "servers", None) or []
        if not servers or not servers[0].sockets:
            raise HealthServiceError("health service started without an accessible socket")
        socket = servers[0].sockets[0]
        host, port = socket.getsockname()[:2]
        return str(host), int(port)


class HealthService:
    def __init__(
        self,
        context: AppContext,
        runner_factory: Callable[[FastAPI, AppConfig], Any] | None = None,
    ) -> None:
        self._context = context
        self._logger = logging.getLogger("qq_ai_bot.health")
        self._app = create_health_app(context)
        factory = runner_factory or UvicornServerRunner
        self._runner = factory(self._app, self._context.config)

    @property
    def asgi_app(self) -> FastAPI:
        return self._app

    async def start(self) -> tuple[str, int]:
        host, port = await self._runner.start()
        self._logger.info("health service started on %s:%s", host, port)
        return host, port

    async def stop(self) -> None:
        await self._runner.stop()
        self._logger.info("health service stopped")


def build_health_payload(context: AppContext) -> dict[str, object]:
    return {
        "status": "ok" if context.runtime.status == "running" else "starting",
        "app_name": context.config.app_name,
        "environment": context.config.environment,
        "http": {
            "host": context.runtime.http_host,
            "port": context.runtime.http_port,
        },
    }


def create_health_app(context: AppContext) -> FastAPI:
    app = FastAPI()

    @app.get(context.config.http.health_path)
    async def healthz() -> JSONResponse:
        return JSONResponse(build_health_payload(context))

    return app
