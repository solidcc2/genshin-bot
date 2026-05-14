from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import AppConfig
from app.errors import ServiceRegistrationError


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        if name in self._services:
            raise ServiceRegistrationError(f"Service already registered: {name}")
        self._services[name] = service

    def get(self, name: str) -> Any:
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services


@dataclass
class RuntimeState:
    status: str = "created"
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    http_host: str | None = None
    http_port: int | None = None

    def mark_started(self, host: str, port: int) -> None:
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self.http_host = host
        self.http_port = port

    def mark_stopped(self) -> None:
        self.status = "stopped"
        self.stopped_at = datetime.now(timezone.utc)


@dataclass
class AppContext:
    config: AppConfig
    logger: logging.Logger
    services: ServiceRegistry = field(default_factory=ServiceRegistry)
    runtime: RuntimeState = field(default_factory=RuntimeState)
