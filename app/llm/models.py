from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class UsageStats:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    model: str


@dataclass
class LLMResult:
    text: str
    usage: UsageStats
    model_used: str
    finish_reason: str
