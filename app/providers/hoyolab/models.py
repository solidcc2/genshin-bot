from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class QRLoginStatus(str, Enum):
    WAITING = "WAITING"
    SCANNED = "SCANNED"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


@dataclass
class QRLoginSession:
    ticket: str
    qr_url: str
    qr_image: bytes
    status: QRLoginStatus
    qr_path: str = ""
    device_id: str = ""
    cookies: dict[str, str] | None = None


@dataclass
class NotesData:
    current_resin: int
    max_resin: int
    resin_recovery_time: str
    current_expeditions: int
    max_expeditions: int
    current_daily_task: int
    max_daily_task: int
    remaining_transformer_recovery: str | None = None
    current_resin_discounts: int = 0
    max_resin_discounts: int = 0

    @property
    def resin_display(self) -> str:
        return f"{self.current_resin}/{self.max_resin}"

    @property
    def expedition_display(self) -> str:
        return f"{self.current_expeditions}/{self.max_expeditions}"


@dataclass
class CheckInResult:
    success: bool
    message: str = ""
    today_signed: bool = False


@dataclass
class ChronicleCharacter:
    name: str
    level: int
    constellation: int
    weapon_name: str
    artifact_set_names: list[str] = field(default_factory=list)


@dataclass
class ChronicleData:
    uid: str
    region: str
    abyss_depth: int | None = None
    characters: list[ChronicleCharacter] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotesResult:
    data: NotesData | None = None
    error: str | None = None


@dataclass
class SignResult:
    data: CheckInResult | None = None
    error: str | None = None


@dataclass
class ChronicleResult:
    data: ChronicleData | None = None
    error: str | None = None
