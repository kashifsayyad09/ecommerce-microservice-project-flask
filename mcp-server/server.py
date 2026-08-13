"""MCP server for the VeeraOps e-commerce platform.

Exposes a small, fixed set of tools (get_my_orders, get_order,
get_order_status, track_order, get_order_items, search_products,
get_product, cancel_order) that the AI agent uses instead of ever touching
the database directly.

Design rules enforced here:
  * No SQL. Every tool calls the existing backend REST API over HTTP.
  * No customer_id is ever trusted from a tool argument for
    customer-scoped tools. Every such tool requires `customer_token`, a
    signed JWT that the *backend* verifies and uses to resolve the
    authenticated customer. mcp-server itself never decodes or trusts the
    token's contents -- it just forwards it, so the backend remains the
    single source of truth for authorization.
  * Tool responses are structured data straight from the backend; the MCP
    server never fabricates order/product information.
"""
import logging
import os
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

import backend_client
from backend_client import BackendError, BackendUnauthorized

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("mcp-server")

mcp = FastMCP(
    name="veeraops-ecommerce-mcp",
    instructions=(
        "Tools for the VeeraOps e-commerce platform. Order tools only ever "
        "return data belonging to the customer identified by the supplied "
        "customer_token; they never accept a raw customer id."
    ),
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8100")),
    stateless_http=True,
)


def _log_tool_call(tool_name: str, started_at: float, ok: bool, extra: str = ""):
    duration_ms = round((time.time() - started_at) * 1000, 1)
    logger.info("mcp_tool tool=%s ok=%s duration_ms=%s %s", tool_name, ok, duration_ms, extra)


def _error_result(exc: Exception) -> dict:
    if isinstance(exc, BackendUnauthorized):
        return {"error": "unauthorized", "message": "Please sign in again to continue."}
    if isinstance(exc, BackendError):
        return {"error": "backend_error", "message": exc.message}
    logger.exception("Unexpected MCP tool failure")
    return {"error": "internal_error", "message": "Something went wrong. Please try again."}


# ---------------------------------------------------------------------------
# Order tools (customer-scoped -- require customer_token)
# ---------------------------------------------------------------------------
@mcp.tool()
def get_my_orders(customer_token: str) -> dict:
    """Return the authenticated customer's recent orders (id, date, total,
    payment status, shipping status, expected delivery, item summary)."""
    started = time.time()
    try:
        result = backend_client.get("/api/me/orders", customer_token=customer_token)
        _log_tool_call("get_my_orders", started, True)
        return result
    except Exception as exc:
        _log_tool_call("get_my_orders", started, False)
        return _error_result(exc)


@mcp.tool()
def get_order(customer_token: str, order_id: int) -> dict:
    """Return full details for one order, only if it belongs to the
    authenticated customer."""
    started = time.time()
    try:
        result = backend_client.get(f"/api/me/orders/{order_id}", customer_token=customer_token)
        _log_tool_call("get_order", started, True, f"order_id={order_id}")
        return result
    except Exception as exc:
        _log_tool_call("get_order", started, False, f"order_id={order_id}")
        return _error_result(exc)


@mcp.tool()
def get_order_status(customer_token: str, order_id: int) -> dict:
    """Return order id, current status, payment status, and expected
    delivery for one order owned by the authenticated customer."""
    started = time.time()
    try:
        result = backend_client.get(f"/api/me/orders/{order_id}/status", customer_token=customer_token)
        _log_tool_call("get_order_status", started, True, f"order_id={order_id}")
        return result
    except Exception as exc:
        _log_tool_call("get_order_status", started, False, f"order_id={order_id}")
        return _error_result(exc)


@mcp.tool()
def track_order(customer_token: str, order_id: int) -> dict:
    """Return shipment/tracking information (tracking number, carrier,
    expected delivery) for one order owned by the authenticated customer."""
    started = time.time()
    try:
        result = backend_client.get(f"/api/me/orders/{order_id}/tracking", customer_token=customer_token)
        _log_tool_call("track_order", started, True, f"order_id={order_id}")
        return result
    except Exception as exc:
        _log_tool_call("track_order", started, False, f"order_id={order_id}")
        return _error_result(exc)


@mcp.tool()
def get_order_items(customer_token: str, order_id: int) -> dict:
    """Return the line items (product, quantity, price, subtotal) for one
    order owned by the authenticated customer."""
    started = time.time()
    try:
        result = backend_client.get(f"/api/me/orders/{order_id}/items", customer_token=customer_token)
        _log_tool_call("get_order_items", started, True, f"order_id={order_id}")
        return result
    except Exception as exc:
        _log_tool_call("get_order_items", started, False, f"order_id={order_id}")
        return _error_result(exc)


@mcp.tool()
def cancel_order(customer_token: str, order_id: int, confirm: bool = False) -> dict:
    """Cancel one order owned by the authenticated customer.

    This is a two-step, confirmation-gated action:
      1. Call with confirm=false (default) to check eligibility. If eligible,
         the result asks for explicit customer confirmation and performs NO
         change.
      2. Only after the customer has explicitly confirmed in the
         conversation, call again with confirm=true to actually cancel.

    The backend independently re-verifies ownership and eligibility every
    time -- this tool cannot cancel an order it does not own or that has
    already shipped/been delivered/been cancelled.
    """
    started = time.time()
    try:
        result = backend_client.post(
            f"/api/me/orders/{order_id}/cancel",
            customer_token=customer_token,
            json_body={"confirm": bool(confirm)},
        )
        _log_tool_call("cancel_order", started, True, f"order_id={order_id} confirm={confirm}")
        return result
    except Exception as exc:
        _log_tool_call("cancel_order", started, False, f"order_id={order_id} confirm={confirm}")
        return _error_result(exc)


# ---------------------------------------------------------------------------
# Product tools (public catalog data, no auth required)
# ---------------------------------------------------------------------------
@mcp.tool()
def search_products(query: str = "", category: str = "", min_price: Optional[float] = None,
                     max_price: Optional[float] = None) -> dict:
    """Search the product catalog by free-text query, category, and/or
    price range. Returns up to 20 matching products."""
    started = time.time()
    try:
        params = {"limit": 20}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        result = backend_client.get("/api/products", params=params)
        _log_tool_call("search_products", started, True, f"query={query!r}")
        return result
    except Exception as exc:
        _log_tool_call("search_products", started, False, f"query={query!r}")
        return _error_result(exc)


@mcp.tool()
def get_product(product_id: str) -> dict:
    """Return details (name, description, price, availability, category,
    image URL) for one product."""
    started = time.time()
    try:
        result = backend_client.get(f"/api/products/{product_id}")
        _log_tool_call("get_product", started, True, f"product_id={product_id}")
        return result
    except Exception as exc:
        _log_tool_call("get_product", started, False, f"product_id={product_id}")
        return _error_result(exc)


# ---------------------------------------------------------------------------
# Health endpoints for Kubernetes probes
# ---------------------------------------------------------------------------
@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready(_request: Request) -> JSONResponse:
    try:
        backend_client.get("/api")
        return JSONResponse({"status": "ready"})
    except Exception as exc:
        return JSONResponse({"status": "not_ready", "reason": str(exc)}, status_code=503)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
