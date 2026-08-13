"""AI Provider Manager: tries Groq -> OpenRouter -> Claude, in that fixed
order, on ANY failure (API error, timeout, rate limit, unavailable model,
auth failure, network failure, service failure). Runs the full multi-step
tool-calling conversation against whichever provider is currently active;
only moves to the next provider if that provider itself fails, not merely
because a tool call inside the conversation returned a business error.
"""
from __future__ import annotations

import logging
import time

from .base import AIProvider, ProviderError, ProviderResult

logger = logging.getLogger("ai-agent.provider_manager")

MAX_TOOL_ITERATIONS = 6


class AllProvidersFailedError(Exception):
    def __init__(self, attempts: list[dict]):
        super().__init__("All AI providers failed")
        self.attempts = attempts


class ProviderManager:
    def __init__(self, providers: list[AIProvider], max_retries_per_provider: int = 1):
        self.providers = providers
        self.max_retries_per_provider = max_retries_per_provider

    async def run_conversation(self, messages: list[dict], tools: list[dict], tool_executor) -> tuple[str, str]:
        """Runs the chat -> (maybe) tool calls -> chat loop against
        providers in priority order. Returns (provider_name, final_text).
        `tool_executor` is an async callable(name, arguments) -> dict.
        """
        attempts = []
        for provider in self.providers:
            conversation = list(messages)  # fresh copy per provider; no cross-provider state reuse
            try:
                final_text = await self._run_with_provider(provider, conversation, tools, tool_executor)
                return provider.name, final_text
            except ProviderError as exc:
                logger.warning(
                    "ai_provider_failed provider=%s category=%s", exc.provider_name, exc.category
                )
                attempts.append({"provider": exc.provider_name, "category": exc.category})
                continue
        raise AllProvidersFailedError(attempts)

    async def _run_with_provider(self, provider: AIProvider, conversation: list[dict], tools: list[dict],
                                  tool_executor) -> str:
        last_exc = None
        for attempt in range(self.max_retries_per_provider + 1):
            try:
                return await self._tool_loop(provider, conversation, tools, tool_executor)
            except ProviderError as exc:
                last_exc = exc
                if exc.category in ("auth", "unavailable_model"):
                    # Not worth retrying the same provider for these.
                    raise
                continue
        raise last_exc

    async def _tool_loop(self, provider: AIProvider, conversation: list[dict], tools: list[dict],
                          tool_executor) -> str:
        for _ in range(MAX_TOOL_ITERATIONS):
            started = time.time()
            result: ProviderResult = await provider.chat(conversation, tools)
            logger.info(
                "ai_provider_call provider=%s stop_reason=%s duration_ms=%s",
                provider.name, result.stop_reason, round((time.time() - started) * 1000, 1),
            )

            if result.stop_reason == "stop":
                return result.text or "I don't have an answer for that right now."

            conversation.append(result.raw_assistant_message)
            for call in result.tool_calls:
                tool_result = await tool_executor(call.name, call.arguments)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _safe_json(tool_result),
                    }
                )
        return "I wasn't able to finish looking that up. Please try rephrasing your question."


def _safe_json(value) -> str:
    import json

    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
