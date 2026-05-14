import json

from app.bootstrap import build_application
from app.http import build_health_payload


class FakeHTTPServer:
    def __init__(self, server_address, handler_class):
        self.server_address = (server_address[0], 18080)
        self.handler_class = handler_class
        self.serving = False
        self.closed = False

    def serve_forever(self):
        self.serving = True

    def shutdown(self):
        self.serving = False

    def server_close(self):
        self.closed = True


def test_application_start_updates_runtime_and_health_payload(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "app_name": "health-test",
                "environment": "test",
                "log_level": "INFO",
                "http": {"host": "127.0.0.1", "port": 0, "health_path": "/healthz"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.http.ThreadingHTTPServer", FakeHTTPServer)

    app = build_application(config_path=config_path, environ={})
    app.start()
    try:
        payload = build_health_payload(app.context)

        assert payload["status"] == "ok"
        assert payload["app_name"] == "health-test"
        assert payload["http"]["port"] == 18080
        assert app.context.services.has("health_service")
    finally:
        app.stop()


def test_application_stop_marks_runtime_stopped(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "app_name": "stop-test",
                "environment": "test",
                "log_level": "INFO",
                "http": {"host": "127.0.0.1", "port": 0, "health_path": "/healthz"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.http.ThreadingHTTPServer", FakeHTTPServer)

    app = build_application(config_path=config_path, environ={})
    app.start()
    app.stop()

    assert app.context.runtime.status == "stopped"
    assert app.context.runtime.stopped_at is not None
