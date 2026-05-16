from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.errors import ConfigError


_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


@dataclass(frozen=True)
class HTTPConfig:
    host: str
    port: int
    health_path: str
    shutdown_timeout: float


@dataclass(frozen=True)
class StorageConfig:
    backend: str
    db_path: str = ""


@dataclass(frozen=True)
class HoYoLABConfig:
    qr_timeout: float
    region: str


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    api_key: str = ""
    endpoint: str = "https://api.deepseek.com/chat/completions"
    default_model: str = "deepseek-v4-flash"
    upgrade_model: str = "deepseek-v4-pro"
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = "你是 genshen，一个智能 AI 助手。"
    timeout: float = 60.0
    max_retries: int = 3


@dataclass(frozen=True)
class OneBotConfig:
    enabled: bool = False
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 18080
    webhook_path: str = "/onebot/v11/"
    api_base: str = "http://127.0.0.1:3000"


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    environment: str
    log_level: str
    http: HTTPConfig
    storage: StorageConfig
    hoyolab: HoYoLABConfig
    onebot: OneBotConfig
    llm: LLMConfig
    providers: dict[str, Any]


class ConfigLoader:
    """Loads configuration from defaults, JSON file, and environment variables."""

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> AppConfig:
        env = dict(os.environ) if environ is None else dict(environ)
        resolved_path = cls._resolve_config_path(config_path, env)
        raw = cls._defaults()

        if resolved_path is not None:
            raw = cls._deep_merge(raw, cls._read_json_config(resolved_path))

        env_overrides = cls._load_env_overrides(env)
        raw = cls._deep_merge(raw, env_overrides)
        return cls._validate(raw)

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "app_name": "qq-ai-bot",
            "environment": "development",
            "log_level": "INFO",
            "http": {
                "host": "127.0.0.1",
                "port": 8000,
                "health_path": "/healthz",
                "shutdown_timeout": 5.0,
            },
            "storage": {
                "backend": "sqlite",
                "db_path": "data/bot.db",
            },
            "providers": {
                "hoyolab": {
                    "qr_timeout": 120.0,
                    "region": "cn",
                },
            },
            "onebot": {
                "enabled": False,
                "webhook_host": "0.0.0.0",
                "webhook_port": 18080,
                "webhook_path": "/onebot/v11/",
                "api_base": "http://127.0.0.1:3000",
            },
            "llm": {
                "enabled": False,
                "api_key": "",
                "endpoint": "https://api.deepseek.com/chat/completions",
                "default_model": "deepseek-v4-flash",
                "upgrade_model": "deepseek-v4-pro",
                "temperature": 0.7,
                "max_tokens": 2048,
                "system_prompt": "你是 genshen，一个智能 AI 助手。",
                "timeout": 60.0,
                "max_retries": 3,
            },
        }

    @staticmethod
    def _resolve_config_path(
        config_path: str | Path | None,
        environ: Mapping[str, str],
    ) -> Path | None:
        candidate = config_path or environ.get("APP_CONFIG_PATH")
        if not candidate:
            return None

        path = Path(candidate)
        if not path.exists():
            raise ConfigError(f"Config file does not exist: {path}")
        if not path.is_file():
            raise ConfigError(f"Config path is not a file: {path}")
        return path

    @staticmethod
    def _read_json_config(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON config in {path}: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Failed to read config file {path}: {exc}") from exc

        if not isinstance(loaded, dict):
            raise ConfigError("Config file root must be a JSON object")
        return loaded

    @staticmethod
    def _load_env_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}

        if "APP_STORAGE_BACKEND" in environ:
            overrides.setdefault("storage", {})["backend"] = environ["APP_STORAGE_BACKEND"]
        if "APP_STORAGE_DB_PATH" in environ:
            overrides.setdefault("storage", {})["db_path"] = environ["APP_STORAGE_DB_PATH"]
        if "APP_NAME" in environ:
            overrides["app_name"] = environ["APP_NAME"]
        if "APP_ENVIRONMENT" in environ:
            overrides["environment"] = environ["APP_ENVIRONMENT"]
        if "APP_LOG_LEVEL" in environ:
            overrides["log_level"] = environ["APP_LOG_LEVEL"]
        if "APP_HTTP_HOST" in environ:
            overrides.setdefault("http", {})["host"] = environ["APP_HTTP_HOST"]
        if "APP_HTTP_PORT" in environ:
            port_value = environ["APP_HTTP_PORT"]
            try:
                overrides.setdefault("http", {})["port"] = int(port_value)
            except ValueError as exc:
                raise ConfigError(f"APP_HTTP_PORT must be an integer: {port_value}") from exc
        if "APP_HTTP_HEALTH_PATH" in environ:
            overrides.setdefault("http", {})["health_path"] = environ["APP_HTTP_HEALTH_PATH"]
        if "APP_HTTP_SHUTDOWN_TIMEOUT" in environ:
            timeout_value = environ["APP_HTTP_SHUTDOWN_TIMEOUT"]
            try:
                overrides.setdefault("http", {})["shutdown_timeout"] = float(timeout_value)
            except ValueError as exc:
                raise ConfigError(
                    f"APP_HTTP_SHUTDOWN_TIMEOUT must be a number: {timeout_value}"
                ) from exc

        if "APP_ONEBOT_ENABLED" in environ:
            overrides.setdefault("onebot", {})["enabled"] = environ["APP_ONEBOT_ENABLED"].lower() == "true"
        if "APP_ONEBOT_WEBHOOK_HOST" in environ:
            overrides.setdefault("onebot", {})["webhook_host"] = environ["APP_ONEBOT_WEBHOOK_HOST"]
        if "APP_ONEBOT_WEBHOOK_PORT" in environ:
            port_value = environ["APP_ONEBOT_WEBHOOK_PORT"]
            try:
                overrides.setdefault("onebot", {})["webhook_port"] = int(port_value)
            except ValueError as exc:
                raise ConfigError(f"APP_ONEBOT_WEBHOOK_PORT must be an integer: {port_value}") from exc
        if "APP_ONEBOT_WEBHOOK_PATH" in environ:
            overrides.setdefault("onebot", {})["webhook_path"] = environ["APP_ONEBOT_WEBHOOK_PATH"]
        if "APP_ONEBOT_API_BASE" in environ:
            overrides.setdefault("onebot", {})["api_base"] = environ["APP_ONEBOT_API_BASE"]

        if "APP_LLM_ENABLED" in environ:
            overrides.setdefault("llm", {})["enabled"] = environ["APP_LLM_ENABLED"].lower() == "true"
        if "APP_LLM_API_KEY" in environ:
            overrides.setdefault("llm", {})["api_key"] = environ["APP_LLM_API_KEY"]
        if "APP_LLM_ENDPOINT" in environ:
            overrides.setdefault("llm", {})["endpoint"] = environ["APP_LLM_ENDPOINT"]
        if "APP_LLM_DEFAULT_MODEL" in environ:
            overrides.setdefault("llm", {})["default_model"] = environ["APP_LLM_DEFAULT_MODEL"]
        if "APP_LLM_UPGRADE_MODEL" in environ:
            overrides.setdefault("llm", {})["upgrade_model"] = environ["APP_LLM_UPGRADE_MODEL"]
        if "APP_LLM_TEMPERATURE" in environ:
            temp_value = environ["APP_LLM_TEMPERATURE"]
            try:
                overrides.setdefault("llm", {})["temperature"] = float(temp_value)
            except ValueError as exc:
                raise ConfigError(f"APP_LLM_TEMPERATURE must be a number: {temp_value}") from exc
        if "APP_LLM_MAX_TOKENS" in environ:
            tokens_value = environ["APP_LLM_MAX_TOKENS"]
            try:
                overrides.setdefault("llm", {})["max_tokens"] = int(tokens_value)
            except ValueError as exc:
                raise ConfigError(f"APP_LLM_MAX_TOKENS must be an integer: {tokens_value}") from exc
        if "APP_LLM_SYSTEM_PROMPT" in environ:
            overrides.setdefault("llm", {})["system_prompt"] = environ["APP_LLM_SYSTEM_PROMPT"]
        if "APP_LLM_TIMEOUT" in environ:
            timeout_value = environ["APP_LLM_TIMEOUT"]
            try:
                overrides.setdefault("llm", {})["timeout"] = float(timeout_value)
            except ValueError as exc:
                raise ConfigError(f"APP_LLM_TIMEOUT must be a number: {timeout_value}") from exc
        if "APP_LLM_MAX_RETRIES" in environ:
            retries_value = environ["APP_LLM_MAX_RETRIES"]
            try:
                overrides.setdefault("llm", {})["max_retries"] = int(retries_value)
            except ValueError as exc:
                raise ConfigError(f"APP_LLM_MAX_RETRIES must be an integer: {retries_value}") from exc

        return overrides

    @classmethod
    def _deep_merge(cls, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _validate(raw: dict[str, Any]) -> AppConfig:
        app_name = raw.get("app_name")
        environment = raw.get("environment")
        log_level = raw.get("log_level")
        http = raw.get("http")
        providers = raw.get("providers", {})

        if not isinstance(app_name, str) or not app_name.strip():
            raise ConfigError("app_name must be a non-empty string")
        if not isinstance(environment, str) or not environment.strip():
            raise ConfigError("environment must be a non-empty string")
        if not isinstance(log_level, str) or log_level.upper() not in _VALID_LOG_LEVELS:
            raise ConfigError(f"log_level must be one of {_VALID_LOG_LEVELS}")
        if not isinstance(http, dict):
            raise ConfigError("http must be an object")
        storage = raw.get("storage", {})
        if not isinstance(storage, dict):
            raise ConfigError("storage must be an object")
        if not isinstance(providers, dict):
            raise ConfigError("providers must be an object")

        host = http.get("host")
        port = http.get("port")
        health_path = http.get("health_path")
        shutdown_timeout = http.get("shutdown_timeout")

        if not isinstance(host, str) or not host.strip():
            raise ConfigError("http.host must be a non-empty string")
        if not isinstance(port, int) or not (0 <= port <= 65535):
            raise ConfigError("http.port must be an integer between 0 and 65535")
        if not isinstance(health_path, str) or not health_path.startswith("/"):
            raise ConfigError("http.health_path must be a string starting with '/'")
        if not isinstance(shutdown_timeout, (int, float)) or shutdown_timeout <= 0:
            raise ConfigError("http.shutdown_timeout must be a positive number")

        storage_backend = storage.get("backend")
        if not isinstance(storage_backend, str) or storage_backend not in ("memory", "sqlite"):
            raise ConfigError("storage.backend must be 'memory' or 'sqlite'")
        storage_db_path = storage.get("db_path", "")
        if storage_backend == "sqlite" and (not isinstance(storage_db_path, str) or not storage_db_path.strip()):
            raise ConfigError("storage.db_path must be a non-empty string when backend is 'sqlite'")

        hoyolab_raw = providers.get("hoyolab", {})
        if not isinstance(hoyolab_raw, dict):
            raise ConfigError("providers.hoyolab must be an object")

        onebot_raw = raw.get("onebot", {})
        if not isinstance(onebot_raw, dict):
            raise ConfigError("onebot must be an object")

        llm_raw = raw.get("llm", {})
        if not isinstance(llm_raw, dict):
            raise ConfigError("llm must be an object")

        return AppConfig(
            app_name=app_name.strip(),
            environment=environment.strip(),
            log_level=log_level.upper(),
            http=HTTPConfig(
                host=host.strip(),
                port=port,
                health_path=health_path,
                shutdown_timeout=float(shutdown_timeout),
            ),
            storage=StorageConfig(
                backend=storage_backend,
                db_path=storage_db_path,
            ),
            hoyolab=HoYoLABConfig(
                qr_timeout=hoyolab_raw.get("qr_timeout", 120.0),
                region=hoyolab_raw.get("region", "cn"),
            ),
            onebot=OneBotConfig(
                enabled=bool(onebot_raw.get("enabled", False)),
                webhook_host=str(onebot_raw.get("webhook_host", "0.0.0.0")),
                webhook_port=int(onebot_raw.get("webhook_port", 18080)),
                webhook_path=str(onebot_raw.get("webhook_path", "/onebot/v11/")),
                api_base=str(onebot_raw.get("api_base", "http://127.0.0.1:3000")),
            ),
            llm=LLMConfig(
                enabled=bool(llm_raw.get("enabled", False)),
                api_key=str(llm_raw.get("api_key", "")),
                endpoint=str(llm_raw.get("endpoint", "https://api.deepseek.com/chat/completions")),
                default_model=str(llm_raw.get("default_model", "deepseek-v4-flash")),
                upgrade_model=str(llm_raw.get("upgrade_model", "deepseek-v4-pro")),
                temperature=float(llm_raw.get("temperature", 0.7)),
                max_tokens=int(llm_raw.get("max_tokens", 2048)),
                system_prompt=str(llm_raw.get("system_prompt", "")),
                timeout=float(llm_raw.get("timeout", 60.0)),
                max_retries=int(llm_raw.get("max_retries", 3)),
            ),
            providers=providers,
        )
