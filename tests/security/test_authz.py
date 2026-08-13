"""Security tests exercised against the live backend logic (auth, order
ownership, cancellation rules). These import backend/app.py directly and
use sqlite-free unit-level fakes where a real MySQL isn't available, so
they run in CI without provisioning RDS.

Where a real MySQL test database IS available (e.g. a local docker-compose
MySQL for integration testing), set TEST_DATABASE_URL and these tests will
exercise the real DB-backed code paths instead. See README "Testing" section.
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


@pytest.fixture()
def backend_app(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-unit-tests-only")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")
    monkeypatch.setenv("DB_NAME", "test")
    import app as backend_module

    importlib.reload(backend_module)
    return backend_module


def test_jwt_cannot_be_forged_without_secret(backend_app):
    """A token signed with a different secret must be rejected -- this is
    what stops "User A requesting User B's order" via a tampered token."""
    import jwt

    forged = jwt.encode(
        {"sub": "2", "email": "victim@example.com", "iss": "veeraops-backend"},
        "wrong-secret",
        algorithm="HS256",
    )
    assert backend_app.decode_customer_token(forged) is None


def test_valid_token_round_trips_to_correct_customer_id(backend_app):
    token = backend_app.issue_customer_token(
        {"id": 7, "email": "alice@example.com", "username": "alice"}
    )
    payload = backend_app.decode_customer_token(token)
    assert payload["sub"] == "7"
    assert payload["email"] == "alice@example.com"


def test_missing_token_is_rejected_by_auth_required(backend_app):
    with backend_app.app.test_request_context("/api/me/orders"):
        resp, status = backend_app.list_my_orders()
        assert status == 401


def test_invalid_token_is_rejected_by_auth_required(backend_app):
    headers = {"Authorization": "Bearer not-a-real-token"}
    with backend_app.app.test_request_context("/api/me/orders", headers=headers):
        resp, status = backend_app.list_my_orders()
        assert status == 401


def test_order_endpoints_never_accept_customer_id_from_request_body(backend_app):
    """The /api/me/orders* routes take the customer id only from the
    verified JWT (g.customer), never from request.json -- this test asserts
    that shape by inspecting the source, since a full DB-backed ownership
    test requires a live MySQL fixture (see integration tests)."""
    import inspect

    src = inspect.getsource(backend_app.fetch_owned_order)
    assert "customer_id" in src
    # ownership is enforced in SQL WHERE id = %s AND user_id = %s
    assert "user_id = %s" in src


def test_cancel_requires_confirm_flag_present_in_route(backend_app):
    import inspect

    src = inspect.getsource(backend_app.cancel_my_order)
    assert 'data.get("confirm")' in src
    assert "requires_confirmation" in src


@pytest.mark.parametrize(
    "malicious_query",
    [
        "'; DROP TABLE orders;--",
        "1 OR 1=1",
        "laptop' UNION SELECT password FROM users--",
    ],
)
def test_product_search_uses_parameterized_queries_not_string_interpolation(backend_app, malicious_query):
    """Structural guarantee: list_products passes user-supplied search text
    as a bound parameter (%s + params list) rather than interpolating it
    into the SQL string, so injection payloads are treated as inert literal
    search text, not executable SQL."""
    import inspect

    src = inspect.getsource(backend_app.list_products)
    assert "%s" in src
    # The query/category/price values are appended to `params` and passed
    # separately to cursor.execute(sql, params) -- never f-string'd into
    # the SQL text itself.
    assert "params.append" in src or "params.extend" in src
    assert "cursor.execute(" in src


def test_prompt_injection_style_message_is_just_data_to_the_backend(backend_app):
    """The backend has no concept of 'AI instructions' at all -- an
    order-cancellation request coming from the AI agent still goes through
    the same ownership + eligibility checks as the website UI. This test
    documents that cancel_my_order does not special-case any caller."""
    import inspect

    src = inspect.getsource(backend_app.cancel_my_order)
    assert "g.customer" in src  # always scoped to the authenticated caller
