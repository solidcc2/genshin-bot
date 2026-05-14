from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.errors import HealthServiceError
from app.runtime import AppContext


class HealthService:
    def __init__(
        self,
        context: AppContext,
        server_class: type[ThreadingHTTPServer] | None = None,
    ) -> None:
        self._context = context
        self._logger = logging.getLogger("qq_ai_bot.health")
        self._server_class = server_class or ThreadingHTTPServer
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> tuple[str, int]:
        if self._server is not None:
            raise RuntimeError("Health service already started")

        handler = _build_handler(self._context, self._context.config.http.health_path)
        try:
            self._server = self._server_class(
                (self._context.config.http.host, self._context.config.http.port),
                handler,
            )
        except OSError as exc:
            raise HealthServiceError(f"failed to start health service: {exc}") from exc
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="health-http-server",
            daemon=True,
        )
        self._thread.start()
        host, port = self._server.server_address[:2]
        self._logger.info("health service started on %s:%s", host, port)
        return str(host), int(port)

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._logger.info("health service stopped")
        self._thread = None
        self._server = None


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


def _build_handler(
    context: AppContext,
    health_path: str,
) -> type[BaseHTTPRequestHandler]:
    class HealthRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != health_path:
                self._send_json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
                return

            payload = build_health_payload(context)
            self._send_json(HTTPStatus.OK, payload)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HealthRequestHandler
