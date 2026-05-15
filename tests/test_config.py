import json

import pytest

from app.config import ConfigLoader
from app.errors import ConfigError


def test_loads_config_file_and_env_override(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "app_name": "test-bot",
                "environment": "test",
                "log_level": "DEBUG",
                "http": {
                    "host": "127.0.0.1",
                    "port": 9001,
                    "health_path": "/ready",
                    "shutdown_timeout": 7.5
                },
            }
        ),
        encoding="utf-8",
    )

    config = ConfigLoader.load(
        config_path=config_path,
        environ={"APP_HTTP_PORT": "9002"},
    )

    assert config.app_name == "test-bot"
    assert config.environment == "test"
    assert config.log_level == "DEBUG"
    assert config.http.port == 9002
    assert config.http.health_path == "/ready"
    assert config.http.shutdown_timeout == 7.5


def test_missing_config_file_raises():
    with pytest.raises(ConfigError, match="does not exist"):
        ConfigLoader.load(config_path="missing.json", environ={})


def test_invalid_env_port_raises():
    with pytest.raises(ConfigError, match="APP_HTTP_PORT must be an integer"):
        ConfigLoader.load(environ={"APP_HTTP_PORT": "abc"})


def test_invalid_config_shape_raises(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "http": {
                    "host": "127.0.0.1",
                    "port": "bad",
                    "health_path": "healthz",
                    "shutdown_timeout": 5.0
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="http.port must be an integer"):
        ConfigLoader.load(config_path=config_path, environ={})


def test_invalid_shutdown_timeout_raises():
    with pytest.raises(ConfigError, match="APP_HTTP_SHUTDOWN_TIMEOUT must be a number"):
        ConfigLoader.load(environ={"APP_HTTP_SHUTDOWN_TIMEOUT": "abc"})


def test_invalid_storage_backend_raises(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "app_name": "test",
            "environment": "test",
            "log_level": "INFO",
            "http": {"host": "0.0.0.0", "port": 8080, "health_path": "/healthz", "shutdown_timeout": 5.0},
            "storage": {"backend": "redis"},
        }),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="storage.backend must be 'memory' or 'sqlite'"):
        ConfigLoader.load(config_path=config_path, environ={})


def test_sqlite_without_db_path_raises(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "app_name": "test",
            "environment": "test",
            "log_level": "INFO",
            "http": {"host": "0.0.0.0", "port": 8080, "health_path": "/healthz", "shutdown_timeout": 5.0},
            "storage": {"backend": "sqlite", "db_path": ""},
        }),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="storage.db_path must be a non-empty string when backend is 'sqlite'"):
        ConfigLoader.load(config_path=config_path, environ={})
