"""Resolves a Bearer token to a customer identity by asking the backend --
ai-agent never decodes or trusts the JWT itself. The backend remains the
single source of truth for authentication; this keeps JWT_SECRET scoped to
one service instead of being duplicated across the platform.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend-service").rstrip("/")
AUTH_TIMEOUT_SECONDS = float(os.getenv("AUTH_TIMEOUT_SECONDS", "5"))


async def resolve_customer(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=AUTH_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{BACKEND_BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return None
    if resp.status_code != 200:
        return None
    return resp.json().get("customer")
