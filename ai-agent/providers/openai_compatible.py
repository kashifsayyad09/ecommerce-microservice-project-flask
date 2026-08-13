"""Shared implementation for OpenAI-compatible chat-completions APIs
(Groq and OpenRouter both speak this format)."""
from __future__ import annotations

import logging

import httpx

from .base import AIProvider, ProviderError, ProviderResult, ToolCall

logger = logging.getLogger("ai-agent.providers")


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, name: str, base_url: str, api_key: str, model: str,
                 request_timeout_seconds: float, extra_headers: dict | None = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.request_timeout_seconds = request_timeout_seconds
        self.extra_headers = extra_headers or {}

    def _to_openai_tools(self, tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    async def chat(self, messages: list[dict], tools: list[dict]) -> ProviderResult:
        if not self.api_key:
            raise ProviderError(self.name, "auth", f"{self.name} API key is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        body = {
            "model": self.model,
            "messages": messages,
            "tools": self._to_openai_tools(tools) if tools else None,
            "tool_choice": "auto" if tools else None,
            "temperature": 0.2,
            "max_tokens": 800,
        }
        body = {k: v for k, v in body.items() if v is not None}

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError(self.name, "timeout", f"{self.name} request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderError(self.name, "network", f"{self.name} network failure") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise ProviderError(self.name, "auth", f"{self.name} authentication failed")
        if resp.status_code == 429:
            raise ProviderError(self.name, "rate_limit", f"{self.name} rate limited")
        if resp.status_code == 404:
            raise ProviderError(self.name, "unavailable_model", f"{self.name} model unavailable")
        if resp.status_code >= 400:
            raise ProviderError(self.name, "http_error", f"{self.name} returned HTTP {resp.status_code}")

        try:
            data = resp.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError(self.name, "unknown", f"{self.name} returned an unexpected response") from exc

        raw_tool_calls = message.get("tool_calls") or []
        if raw_tool_calls:
            import json as _json

            calls = []
            for tc in raw_tool_calls:
                try:
                    args = _json.loads(tc["function"]["arguments"] or "{}")
                except ValueError:
                    args = {}
                calls.append(ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=args))
            return ProviderResult(stop_reason="tool_calls", tool_calls=calls, raw_assistant_message=message)

        return ProviderResult(stop_reason="stop", text=message.get("content") or "", raw_assistant_message=message)
