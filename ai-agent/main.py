"""AI agent service: receives chat requests from the storefront, resolves
the authenticated customer, runs the Groq -> OpenRouter -> Claude failover
conversation against MCP tools, and returns a clean response. Never exposes
provider errors, stack traces, or credentials to the browser.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import auth
import mcp_client
import tools
from providers import (
    AllProvidersFailedError,
    ClaudeProvider,
    ProviderManager,
    build_groq_provider,
    build_openrouter_provider,
)
from system_prompt import SYSTEM_PROMPT

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ai-agent")

AI_REQUEST_TIMEOUT = float(os.getenv("AI_REQUEST_TIMEOUT", "25"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "1"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="VeeraOps AI Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

_provider_manager = ProviderManager(
    providers=[
        build_groq_provider(AI_REQUEST_TIMEOUT),
        build_openrouter_provider(AI_REQUEST_TIMEOUT),
        ClaudeProvider(AI_REQUEST_TIMEOUT),
    ],
    max_retries_per_provider=AI_MAX_RETRIES,
)

# Simple in-memory sliding-window rate limiter, keyed by client identity.
# Fine for a single-instance/dev setup; swap for a shared store (Redis) if
# ai-agent is scaled to multiple replicas behind the ClusterIP service.
_rate_limit_buckets: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(key: str):
    now = time.time()
    bucket = _rate_limit_buckets[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a moment.")
    bucket.append(now)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=tools.MAX_PROMPT_LENGTH)


class ChatResponse(BaseModel):
    success: bool
    provider: str | None = None
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        await mcp_client.list_tool_specs()
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="mcp-server unavailable") from exc


@app.post("/api/ai/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, authorization: str | None = Header(default=None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()

    client_key = token or (request.client.host if request.client else "anonymous")
    _check_rate_limit(client_key)

    if len(payload.message) > tools.MAX_PROMPT_LENGTH:
        raise HTTPException(status_code=400, detail="Message is too long.")

    customer = await auth.resolve_customer(token)
    authenticated = customer is not None
    # Re-derive the token we trust for tool calls strictly from a
    # successfully-verified customer -- never forward an unverified token.
    verified_token = token if authenticated else None

    try:
        mcp_tool_specs = await mcp_client.list_tool_specs()
    except Exception:
        logger.exception("mcp_list_tools_failed")
        return ChatResponse(success=False, message="The assistant is temporarily unavailable. Please try again shortly.")

    llm_tools = tools.build_llm_tool_specs(mcp_tool_specs, authenticated=authenticated)
    executor = tools.ToolExecutor(customer_token=verified_token)

    system_content = SYSTEM_PROMPT
    if authenticated:
        system_content += f"\nThe currently signed-in customer's first name/username is: {customer.get('username') or customer.get('full_name') or 'the customer'}."
    else:
        system_content += "\nNo customer is currently signed in."

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": payload.message},
    ]

    try:
        provider_name, final_text = await _provider_manager.run_conversation(messages, llm_tools, executor)
        return ChatResponse(success=True, provider=provider_name, message=final_text)
    except AllProvidersFailedError:
        logger.error("all_ai_providers_failed")
        return ChatResponse(
            success=False,
            message="The assistant is temporarily unavailable. Please try again in a few minutes.",
        )
    except Exception:  # noqa: BLE001 -- never leak internals to the browser
        logger.exception("chat_request_failed")
        return ChatResponse(success=False, message="Something went wrong. Please try again.")
