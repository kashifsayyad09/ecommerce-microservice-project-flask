"""Thin HTTP client for the existing Flask backend.

This is the ONLY place mcp-server talks to application data. It never
touches MySQL/RDS directly and never runs SQL of any kind -- every read or
write goes through the existing, already-authorized backend REST API. This
keeps the AI/MCP layer strictly a "controlled tool layer" on top of the
application's real business logic, per the project's security requirements.
"""
import os
from typing import Any, Optional

import httpx

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend-service").rstrip("/")
BACKEND_TIMEOUT_SECONDS = float(os.getenv("BACKEND_TIMEOUT_SECONDS", "8"))


class BackendError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class BackendUnauthorized(BackendError):
    pass


def _headers(customer_token: Optional[str]) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if customer_token:
        headers["Authorization"] = f"Bearer {customer_token}"
    return headers


def _handle_response(resp: httpx.Response) -> dict:
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    if resp.status_code == 401:
        raise BackendUnauthorized(401, payload.get("error", "Authentication required"))
    if resp.status_code >= 400:
        raise BackendError(resp.status_code, payload.get("error", f"Backend error ({resp.status_code})"))
    return payload


def get(path: str, customer_token: Optional[str] = None, params: Optional[dict] = None) -> dict:
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        resp = client.get(f"{BACKEND_BASE_URL}{path}", headers=_headers(customer_token), params=params)
    return _handle_response(resp)


def post(path: str, customer_token: Optional[str] = None, json_body: Optional[dict] = None) -> dict:
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        resp = client.post(f"{BACKEND_BASE_URL}{path}", headers=_headers(customer_token), json=json_body or {})
    return _handle_response(resp)
