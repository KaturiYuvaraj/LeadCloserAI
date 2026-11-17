"""
With AUTH_STRICT=true (production) the public pages and the phone webhooks must still answer
without a login, and private data must not. Offline.
"""

import pytest
from starlette.testclient import TestClient

import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "true")
    monkeypatch.delenv("VOBIZ_WEBHOOK_SECRET", raising=False)
    return TestClient(main.app, follow_redirects=False)


@pytest.mark.parametrize("path", ["/", "/login", "/static/js/app.js"])
def test_public_pages_open_without_login(client, path):
    assert client.get(path).status_code == 200, path


def test_dashboard_sends_logged_out_visitors_to_login(client):
    r = client.get("/crm")
    assert r.status_code == 302 and r.headers["location"].startswith("/login")


def test_login_form_reaches_the_server(client):
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r.status_code in (400, 401) and "Authentication required" not in r.text


def test_private_data_needs_login(client):
    for path in ("/api/auth/me", "/api/inbound/hours", "/api/dialer/engine"):
        assert client.get(path).status_code == 401, path


def test_phone_webhooks_do_not_need_a_login(client):
    assert client.post("/api/voice/vobiz/answer", data={"CallUUID": "x", "From": "+919000000001"}).status_code == 200
