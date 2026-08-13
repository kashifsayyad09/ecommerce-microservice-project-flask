"""MCP client used by the AI agent to call mcp-server tools.

Opens a fresh streamable-HTTP MCP session per call. This is not the most
efficient possible pattern, but it keeps request isolation simple and
correct under concurrent chat requests from different customers, which
matters more here than raw throughput.
"""
from __future__ import annotations

import logging
import os
import json
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger("ai-agent.mcp_client")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server-service:8100/mcp/")
MCP_TOOL_TIMEOUT_SECONDS = float(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", "10"))


class MCPToolError(Exception):
    pass


async def list_tool_specs() -> list[dict]:
    """Returns [{name, description, input_schema}, ...] for every tool the
    MCP server exposes. Used once at startup / cache refresh to build the
    tool schemas shown to the LLM providers."""
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
                for tool in result.tools
            ]


async def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict:
    """Calls one MCP tool and returns its structured result as a dict.
    Raises MCPToolError on transport-level failure (server unreachable,
    timeout, protocol error) -- NOT on a normal business-logic error result
    (like "order not found"), which the tool itself returns as data."""
    try:
        async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    except Exception as exc:  # transport failure
        logger.warning("mcp_transport_error tool=%s error=%s", tool_name, type(exc).__name__)
        raise MCPToolError(f"MCP server unavailable while calling {tool_name}") from exc

    if result.isError:
        text = _extract_text(result)
        return {"error": "tool_error", "message": text or f"{tool_name} failed"}

    text = _extract_text(result)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}
    except (ValueError, TypeError):
        return {"message": text}


def _extract_text(result) -> Optional[str]:
    for block in result.content or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return None
