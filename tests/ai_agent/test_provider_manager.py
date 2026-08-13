import pytest

from providers.base import AIProvider, ProviderError, ProviderResult, ToolCall
from providers.manager import AllProvidersFailedError, ProviderManager


class FakeProvider(AIProvider):
    """Scriptable fake provider: `behaviors` is a list of either a
    ProviderError to raise, or a ProviderResult to return, consumed one per
    call to chat()."""

    def __init__(self, name, behaviors):
        self.name = name
        self.behaviors = list(behaviors)
        self.calls = 0

    async def chat(self, messages, tools):
        self.calls += 1
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


async def noop_executor(name, arguments):
    return {"ok": True}


@pytest.mark.asyncio
async def test_groq_success_first_try():
    groq = FakeProvider("groq", [ProviderResult(stop_reason="stop", text="Hi from groq")])
    manager = ProviderManager(providers=[groq], max_retries_per_provider=0)

    provider_name, text = await manager.run_conversation([{"role": "user", "content": "hi"}], [], noop_executor)

    assert provider_name == "groq"
    assert text == "Hi from groq"


@pytest.mark.asyncio
async def test_groq_timeout_falls_back_to_openrouter():
    groq = FakeProvider("groq", [ProviderError("groq", "timeout", "timed out")])
    openrouter = FakeProvider("openrouter", [ProviderResult(stop_reason="stop", text="Hi from openrouter")])
    manager = ProviderManager(providers=[groq, openrouter], max_retries_per_provider=0)

    provider_name, text = await manager.run_conversation([{"role": "user", "content": "hi"}], [], noop_executor)

    assert provider_name == "openrouter"
    assert text == "Hi from openrouter"


@pytest.mark.asyncio
async def test_groq_rate_limited_falls_back_to_openrouter():
    groq = FakeProvider("groq", [ProviderError("groq", "rate_limit", "429")])
    openrouter = FakeProvider("openrouter", [ProviderResult(stop_reason="stop", text="ok")])
    manager = ProviderManager(providers=[groq, openrouter], max_retries_per_provider=0)

    provider_name, _ = await manager.run_conversation([], [], noop_executor)
    assert provider_name == "openrouter"


@pytest.mark.asyncio
async def test_groq_and_openrouter_fail_falls_back_to_claude():
    groq = FakeProvider("groq", [ProviderError("groq", "network", "dns failure")])
    openrouter = FakeProvider("openrouter", [ProviderError("openrouter", "http_error", "503")])
    claude = FakeProvider("claude", [ProviderResult(stop_reason="stop", text="Hi from claude")])
    manager = ProviderManager(providers=[groq, openrouter, claude], max_retries_per_provider=0)

    provider_name, text = await manager.run_conversation([], [], noop_executor)

    assert provider_name == "claude"
    assert text == "Hi from claude"


@pytest.mark.asyncio
async def test_all_providers_unavailable_raises_clean_error():
    groq = FakeProvider("groq", [ProviderError("groq", "auth", "bad key")])
    openrouter = FakeProvider("openrouter", [ProviderError("openrouter", "unavailable_model", "no model")])
    claude = FakeProvider("claude", [ProviderError("claude", "timeout", "timed out")])
    manager = ProviderManager(providers=[groq, openrouter, claude], max_retries_per_provider=0)

    with pytest.raises(AllProvidersFailedError) as excinfo:
        await manager.run_conversation([], [], noop_executor)

    categories = [a["category"] for a in excinfo.value.attempts]
    assert categories == ["auth", "unavailable_model", "timeout"]


@pytest.mark.asyncio
async def test_tool_call_loop_executes_tool_then_returns_final_text():
    tool_call = ToolCall(id="call_1", name="search_products", arguments={"query": "laptop"})
    groq = FakeProvider(
        "groq",
        [
            ProviderResult(
                stop_reason="tool_calls",
                tool_calls=[tool_call],
                raw_assistant_message={"role": "assistant", "tool_calls": [{"id": "call_1"}]},
            ),
            ProviderResult(stop_reason="stop", text="Here are some laptops."),
        ],
    )
    manager = ProviderManager(providers=[groq], max_retries_per_provider=0)

    executed = []

    async def executor(name, arguments):
        executed.append((name, arguments))
        return {"products": [{"name": "ThinkPad"}]}

    provider_name, text = await manager.run_conversation(
        [{"role": "user", "content": "find laptops"}], [{"name": "search_products"}], executor
    )

    assert provider_name == "groq"
    assert text == "Here are some laptops."
    assert executed == [("search_products", {"query": "laptop"})]


@pytest.mark.asyncio
async def test_auth_failure_does_not_retry_same_provider():
    groq = FakeProvider("groq", [ProviderError("groq", "auth", "bad key")])
    openrouter = FakeProvider("openrouter", [ProviderResult(stop_reason="stop", text="ok")])
    manager = ProviderManager(providers=[groq, openrouter], max_retries_per_provider=2)

    await manager.run_conversation([], [], noop_executor)
    assert groq.calls == 1  # no wasted retries on an auth failure
