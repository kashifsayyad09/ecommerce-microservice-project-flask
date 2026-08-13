"""Bridges MCP tools to the LLM providers.

Security-critical bit: `customer_token` is a required argument on every
order-scoped MCP tool, but the LLM must NEVER be the one supplying it --
that would mean trusting model output (which can be manipulated by
prompt injection in the conversation) to decide whose orders to fetch.
So we strip `customer_token` out of the JSON schema shown to the model,
and `execute_tool` injects the *real*, server-verified token itself right
before calling MCP. The model can only choose which tool to call and
supply the ordinary business parameters (order_id, query, confirm, ...).
"""
from __future__ import annotations

import logging

import mcp_client

logger = logging.getLogger("ai-agent.tools")

HIDDEN_PARAMS = {"customer_token"}

# Tools that require an authenticated customer at all -- if the request
# isn't authenticated, these are omitted entirely from what we show the LLM.
CUSTOMER_SCOPED_TOOLS = {
    "get_my_orders",
    "get_order",
    "get_order_status",
    "track_order",
    "get_order_items",
    "cancel_order",
}

MAX_PROMPT_LENGTH = 2000


def build_llm_tool_specs(mcp_tool_specs: list[dict], authenticated: bool) -> list[dict]:
    specs = []
    for tool in mcp_tool_specs:
        if tool["name"] in CUSTOMER_SCOPED_TOOLS and not authenticated:
            continue
        schema = dict(tool["input_schema"])
        properties = dict(schema.get("properties", {}))
        for hidden in HIDDEN_PARAMS:
            properties.pop(hidden, None)
        schema["properties"] = properties
        schema["required"] = [r for r in schema.get("required", []) if r not in HIDDEN_PARAMS]
        specs.append({"name": tool["name"], "description": tool["description"], "input_schema": schema})
    return specs


class ToolExecutor:
    def __init__(self, customer_token: str | None):
        self.customer_token = customer_token

    async def __call__(self, name: str, arguments: dict) -> dict:
        call_args = dict(arguments)
        if name in CUSTOMER_SCOPED_TOOLS:
            if not self.customer_token:
                return {"error": "unauthorized", "message": "Please sign in to ask about your orders."}
            call_args["customer_token"] = self.customer_token
        try:
            return await mcp_client.call_tool(name, call_args)
        except mcp_client.MCPToolError:
            return {"error": "tool_unavailable", "message": "That information isn't available right now."}
