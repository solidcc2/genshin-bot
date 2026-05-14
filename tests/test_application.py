import json

import httpx
import pytest

from app.bootstrap import build_application
from app.http import build_health_payload


class FakeServerRunner:
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True
        return self.config.http.host, 18080

    async def stop(self):
        self.stopped = True


@pytest.mark.anyio
async def test_application_start_updates_runtime_and_health_payload(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "app_name": "health-test",
                "environment": "test",
                "log_level": "INFO",
                "http": {
                    "host": "127.0.0.1",
                    "port": 0,
                    "health_path": "/healthz",
                    "shutdown_timeout": 5.0,
                },
            }
        ),
        encoding="utf-8",
    )

    app = build_application(
        config_path=config_path,
        environ={},
        health_runner_factory=FakeServerRunner,
    )
    await app.start()
    try:
        payload = build_health_payload(app.context)
        health_service = app.context.services.get("health_service")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=health_service.asgi_app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/healthz")

        assert payload["status"] == "ok"
        assert payload["app_name"] == "health-test"
        assert payload["http"]["port"] == 18080
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        await app.stop()


@pytest.mark.anyio
async def test_application_stop_marks_runtime_stopped(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "app_name": "stop-test",
                "environment": "test",
                "log_level": "INFO",
                "http": {
                    "host": "127.0.0.1",
                    "port": 0,
                    "health_path": "/healthz",
                    "shutdown_timeout": 5.0,
                },
            }
        ),
        encoding="utf-8",
    )

    app = build_application(
        config_path=config_path,
        environ={},
        health_runner_factory=FakeServerRunner,
    )
    await app.start()
    await app.stop()

    assert app.context.runtime.status == "stopped"
    assert app.context.runtime.stopped_at is not None
