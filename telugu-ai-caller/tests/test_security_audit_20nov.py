"""
20 Nov security audit: with AUTH_STRICT=true (production) nothing that changes data, spends Sarvam credits or
shows customer data may answer without a login (or, for the developer API, a valid API key).
Offline: a throwaway test database, no real keys.
"""

import pytest
from starlette.testclient import TestClient

import main


@pytest.fixture
def anon(monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "true")
    monkeypatch.delenv("SIGNUP_ENABLED", raising=False)
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/campaign/pause"), ("POST", "/api/campaign/resume"), ("POST", "/api/campaign/stop"),
    ("GET", "/api/campaign/status"), ("POST", "/api/campaign/start"),
    ("POST", "/api/employees/generate"), ("POST", "/api/employees/1/activate"), ("POST", "/api/employees/1/approve"),
    ("POST", "/api/employees/1/test"), ("POST", "/api/employees/1/knowledge"),
    ("POST", "/api/integrations/providers/telephony/vobiz"), ("POST", "/api/integrations/providers/telephony/vobiz/test"),
    ("GET", "/api/integrations/providers"), ("POST", "/api/profile"),
    ("POST", "/api/tts/test"), ("POST", "/api/leads/discover"),
    ("POST", "/api/calendar/book"), ("GET", "/api/calendar/availability"), ("POST", "/api/messaging/whatsapp/send"),
    ("GET", "/api/v1/keys"), ("POST", "/api/v1/keys"), ("DELETE", "/api/v1/keys/1"),
    ("GET", "/api/v1/billing/orders"), ("POST", "/api/v1/billing/purchase-credits"),
    ("GET", "/api/v1/calls/1/intelligence"), ("POST", "/api/v1/calls/dispatch"),
    ("POST", "/api/dialer/campaigns"), ("POST", "/api/dialer/stop"),
])
def test_closed_without_login(anon, method, path):
    assert anon.request(method, path, json={}).status_code == 401, path


def test_dispatch_needs_a_real_key_not_the_primary_one(anon):
    # it used to fall back to the account's primary key when the caller sent none or a wrong one
    r = anon.post("/api/v1/calls/dispatch", json={"phone": "+919000000001"}, headers={"x-api-key": "lc_live_wrong"})
    assert r.status_code == 401


def test_sign_up_is_closed_by_default(anon):
    r = anon.post("/api/auth/register", json={"company_name": "Stranger Co", "email": "x@example.com",
                                             "password": "Str0ng!Passw0rd"})
    assert r.status_code == 403


def test_self_signup_is_never_approved_for_calling():
    import inspect
    from routers import auth
    assert "calling_approved=False" in inspect.getsource(auth.api_register)


def test_homepage_demo_voices_only_its_samples(anon, monkeypatch):
    from routers import pages

    async def fake_tts(text, speaker=None, **kwargs):
        return b"RIFF-demo"
    monkeypatch.setattr("services.sarvam_service.sarvam_client.text_to_speech", fake_tts)
    pages._demo_audio.clear()
    ok = anon.post("/api/tts/demo", json={"speaker": "simran_en_sales",
                                          "text": "Hello! This is Simran from S P Associates. We specialize in custom software development and AI automation."})
    assert ok.status_code == 200 and ok.content == b"RIFF-demo"
    for bad in ({"speaker": "simran_en_sales", "text": "Read this long text for free"},
                {"speaker": "someone_else", "text": "Hello! This is Simran from S P Associates. We specialize in custom software development and AI automation."}):
        assert anon.post("/api/tts/demo", json=bad).status_code == 403


def test_public_pages_and_webhooks_still_open(anon):
    for path in ("/", "/login"):
        assert anon.get(path).status_code == 200, path
    assert anon.post("/api/voice/vobiz/answer", data={"CallUUID": "x"}).status_code == 200


def test_outbound_call_needs_login_whatever_the_provider(anon):
    # naming another provider used to skip the login check
    for body in ({"lead_id": 1, "phone": "+919000000001"}, {"lead_id": 1, "phone": "+919000000001", "provider": "exotel"}):
        assert anon.post("/api/call/outbound", json=body).status_code == 401
