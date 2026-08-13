"""Shared types + abstract interface for AI providers.

Every concrete provider (Groq, OpenRouter, Claude) implements `chat()` and
returns a normalized ProviderResult, so the failover manager and the tool
loop never need to know which provider answered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderResult:
    stop_reason: str  # "tool_calls" | "stop"
    text: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_assistant_message: Any = None  # provider-native message, to append to history


class ProviderError(Exception):
    """Raised for ANY failure that should trigger failover to the next
    provider: HTTP error, timeout, rate limit, auth failure, bad response
    shape, unavailable model, network failure."""

    def __init__(self, provider_name: str, category: str, message: str):
        super().__init__(message)
        self.provider_name = provider_name
        self.category = category  # "timeout" | "rate_limit" | "auth" | "http_error" | "network" | "unknown"
        self.message = message


class AIProvider:
    name = "base"

    async def chat(self, messages: list[dict], tools: list[dict]) -> ProviderResult:
        raise NotImplementedError
