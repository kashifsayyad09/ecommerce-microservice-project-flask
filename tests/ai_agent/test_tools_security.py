"""Security-relevant tests for the tool bridge: the LLM must never be able
to supply/see customer_token, and unauthenticated sessions must never reach
a customer-scoped tool."""
import pytest

import mcp_client
import tools


MCP_TOOL_SPECS = [
    {
        "name": "get_my_orders",
        "description": "Get my orders",
        "input_schema": {
            "type": "object",
            "properties": {"customer_token": {"type": "string"}},
            "required": ["customer_token"],
        },
    },
    {
        "name": "search_products",
        "description": "Search products",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        },
    },
]


def test_customer_token_is_stripped_from_llm_facing_schema():
    specs = tools.build_llm_tool_specs(MCP_TOOL_SPECS, authenticated=True)
    order_tool = next(s for s in specs if s["name"] == "get_my_orders")
    assert "customer_token" not in order_tool["input_schema"]["properties"]
    assert "customer_token" not in order_tool["input_schema"]["required"]


def test_customer_scoped_tools_hidden_when_unauthenticated():
    specs = tools.build_llm_tool_specs(MCP_TOOL_SPECS, authenticated=False)
    names = [s["name"] for s in specs]
    assert "get_my_orders" not in names
    assert "search_products" in names


@pytest.mark.asyncio
async def test_tool_executor_blocks_customer_scoped_call_without_token(monkeypatch):
    called = {"n": 0}

    async def fake_call_tool(name, arguments):
        called["n"] += 1
        return {}

    monkeypatch.setattr(mcp_client, "call_tool", fake_call_tool)

    executor = tools.ToolExecutor(customer_token=None)
    result = await executor("get_my_orders", {})

    assert result["error"] == "unauthorized"
    assert called["n"] == 0  # MCP was never even contacted


@pytest.mark.asyncio
async def test_tool_executor_injects_real_token_not_model_supplied_one(monkeypatch):
    seen = {}

    async def fake_call_tool(name, arguments):
        seen["arguments"] = arguments
        return {"orders": []}

    monkeypatch.setattr(mcp_client, "call_tool", fake_call_tool)

    executor = tools.ToolExecutor(customer_token="real-verified-token")
    # Simulate a prompt-injected/model-supplied attempt to override the token
    await executor("get_my_orders", {"customer_token": "attacker-supplied-token"})

    assert seen["arguments"]["customer_token"] == "real-verified-token"


@pytest.mark.asyncio
async def test_tool_executor_never_raises_on_mcp_transport_failure(monkeypatch):
    async def fake_call_tool(name, arguments):
        raise mcp_client.MCPToolError("server unreachable")

    monkeypatch.setattr(mcp_client, "call_tool", fake_call_tool)

    executor = tools.ToolExecutor(customer_token="tok")
    result = await executor("search_products", {"query": "phone"})

    assert result["error"] == "tool_unavailable"
