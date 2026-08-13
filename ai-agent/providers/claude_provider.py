"""Claude provider (Anthropic Messages API). Kept as the last-resort
fallback per the required priority: Groq -> OpenRouter -> Claude.

The Anthropic Messages API has a different shape than the OpenAI-style
chat-completions format used by Groq/OpenRouter (separate `system` field,
`tool_use`/`tool_result` content blocks instead of `tool_calls`), so this
provider converts our canonical OpenAI-style message list on the way in
and normalizes the response on the way out.
"""
from __future__ import annotations

import json
import os

import httpx

from .base import AIProvider, ProviderError, ProviderResult, ToolCall

ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, request_timeout_seconds: float):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        self.request_timeout_seconds = request_timeout_seconds

    def _to_anthropic_tools(self, tools: list[dict]) -> list[dict]:
        return [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]

    def _to_anthropic_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_text = ""
        converted: list[dict] = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_text += (msg.get("content") or "") + "\n"
            elif role == "user":
                converted.append({"role": "user", "content": msg.get("content") or ""})
            elif role == "assistant":
                if msg.get("tool_calls"):
                    blocks = []
                    if msg.get("content"):
                        blocks.append({"type": "text", "text": msg["content"]})
                    for tc in msg["tool_calls"]:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "input": json.loads(tc["function"]["arguments"] or "{}"),
                            }
                        )
                    converted.append({"role": "assistant", "content": blocks})
                else:
                    converted.append({"role": "assistant", "content": msg.get("content") or ""})
            elif role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg["tool_call_id"],
                                "content": msg.get("content") or "",
                            }
                        ],
                    }
                )
        return system_text.strip(), converted

    async def chat(self, messages: list[dict], tools: list[dict]) -> ProviderResult:
        if not self.api_key:
            raise ProviderError(self.name, "auth", "Claude API key is not configured")

        system_text, anthropic_messages = self._to_anthropic_messages(messages)
        body = {
            "model": self.model,
            "max_tokens": 800,
            "system": system_text,
            "messages": anthropic_messages,
        }
        if tools:
            body["tools"] = self._to_anthropic_tools(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError(self.name, "timeout", "Claude request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderError(self.name, "network", "Claude network failure") from exc

        if resp.status_code in (401, 403):
            raise ProviderError(self.name, "auth", "Claude authentication failed")
        if resp.status_code == 429:
            raise ProviderError(self.name, "rate_limit", "Claude rate limited")
        if resp.status_code == 404:
            raise ProviderError(self.name, "unavailable_model", "Claude model unavailable")
        if resp.status_code >= 400:
            raise ProviderError(self.name, "http_error", f"Claude returned HTTP {resp.status_code}")

        try:
            data = resp.json()
            content_blocks = data["content"]
        except (KeyError, ValueError) as exc:
            raise ProviderError(self.name, "unknown", "Claude returned an unexpected response") from exc

        tool_calls = []
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_calls.append(ToolCall(id=block["id"], name=block["name"], arguments=block.get("input") or {}))
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        if tool_calls:
            openai_style_message = {
                "role": "assistant",
                "content": "\n".join(text_parts) or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in tool_calls
                ],
            }
            return ProviderResult(
                stop_reason="tool_calls",
                text="\n".join(text_parts) or None,
                tool_calls=tool_calls,
                raw_assistant_message=openai_style_message,
            )
        return ProviderResult(stop_reason="stop", text="\n".join(text_parts))
