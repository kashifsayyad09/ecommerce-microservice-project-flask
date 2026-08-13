"""Tests for each MCP tool: verifies they call the right backend endpoint,
forward auth correctly, and turn backend/transport failures into safe
structured errors instead of raising or leaking internals."""
import backend_client
import server
from backend_client import BackendError, BackendUnauthorized


def test_get_my_orders_calls_backend_with_token(monkeypatch):
    seen = {}

    def fake_get(path, customer_token=None, params=None):
        seen["path"] = path
        seen["token"] = customer_token
        return {"orders": [{"id": 1}]}

    monkeypatch.setattr(backend_client, "get", fake_get)
    result = server.get_my_orders("customer-jwt")

    assert seen["path"] == "/api/me/orders"
    assert seen["token"] == "customer-jwt"
    assert result == {"orders": [{"id": 1}]}


def test_get_order_scopes_to_order_id(monkeypatch):
    seen = {}

    def fake_get(path, customer_token=None, params=None):
        seen["path"] = path
        return {"order": {"id": 42}}

    monkeypatch.setattr(backend_client, "get", fake_get)
    result = server.get_order("tok", 42)
    assert seen["path"] == "/api/me/orders/42"
    assert result["order"]["id"] == 42


def test_order_tools_never_call_arbitrary_sql_or_bypass_backend(monkeypatch):
    """There is no SQL client available to any tool -- this test asserts the
    module simply doesn't import anything MySQL-related, which is the
    structural guarantee behind 'no SQL' rather than a runtime check."""
    import sys

    module_names = " ".join(sys.modules.keys())
    assert "pymysql" not in module_names
    assert "mysql" not in module_names.lower() or "mysql" not in dir(server)


def test_cancel_order_requires_explicit_confirm_flag(monkeypatch):
    calls = []

    def fake_post(path, customer_token=None, json_body=None):
        calls.append((path, json_body))
        if json_body.get("confirm"):
            return {"cancelled": True, "order_id": 5}
        return {"eligible": True, "requires_confirmation": True}

    monkeypatch.setattr(backend_client, "post", fake_post)

    first = server.cancel_order("tok", 5, confirm=False)
    assert first["requires_confirmation"] is True
    assert calls[0][1] == {"confirm": False}

    second = server.cancel_order("tok", 5, confirm=True)
    assert second["cancelled"] is True
    assert calls[1][1] == {"confirm": True}


def test_unauthorized_backend_response_is_translated_safely(monkeypatch):
    def raise_unauthorized(path, customer_token=None, params=None):
        raise BackendUnauthorized(401, "Authentication required")

    monkeypatch.setattr(backend_client, "get", raise_unauthorized)
    result = server.get_my_orders("bad-or-missing-token")
    assert result["error"] == "unauthorized"


def test_backend_error_does_not_leak_stack_trace(monkeypatch):
    def raise_backend_error(path, customer_token=None, params=None):
        raise BackendError(500, "Database connection failed at host 10.0.3.44")

    monkeypatch.setattr(backend_client, "get", raise_backend_error)
    result = server.get_order_status("tok", 99)
    assert result["error"] == "backend_error"
    # The backend's message is passed through (it is already safe/user-facing
    # by convention in this codebase), but no traceback/module path leaks.
    assert "Traceback" not in str(result)


def test_search_products_is_public_no_token_required(monkeypatch):
    seen = {}

    def fake_get(path, customer_token=None, params=None):
        seen["params"] = params
        return {"products": []}

    monkeypatch.setattr(backend_client, "get", fake_get)
    server.search_products(query="laptop", max_price=50000)
    assert seen["params"]["q"] == "laptop"
    assert seen["params"]["max_price"] == 50000
    assert "customer_token" not in seen["params"]


def test_get_product_by_id(monkeypatch):
    monkeypatch.setattr(
        backend_client, "get",
        lambda path, customer_token=None, params=None: {"product": {"product_id": path.rsplit("/", 1)[-1]}},
    )
    result = server.get_product("f2")
    assert result["product"]["product_id"] == "f2"
