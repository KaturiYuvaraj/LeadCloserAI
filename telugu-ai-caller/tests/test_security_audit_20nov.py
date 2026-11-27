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


def test_new_leads_target_includes_leads_marked_new_again():
    # 20 Nov: importing known numbers set them back to NEW, but "New leads" only took never-called leads
    from core.db import SessionLocal
    from models import Call, Lead
    from routers.dialer import resolve_targets
    s = SessionLocal()
    try:
        called_new = Lead(account_id=1, name="Again", phone_e164="+919000000301", variables={"status": "NEW"})
        called_old = Lead(account_id=1, name="Done", phone_e164="+919000000302", variables={"status": "CONTACTED"})
        fresh = Lead(account_id=1, name="Fresh", phone_e164="+919000000303", variables={})
        s.add_all([called_new, called_old, fresh]); s.commit()
        s.add_all([Call(account_id=1, lead_id=called_new.id), Call(account_id=1, lead_id=called_old.id)]); s.commit()
        ids = resolve_targets("new")
        assert called_new.id in ids and fresh.id in ids and called_old.id not in ids
    finally:
        s.close()


def test_test_numbers_skip_the_gap_and_weekly_limit_but_customers_do_not(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from core.db import SessionLocal
    from models import Account, Call, Lead
    from voice_agent.rules import IST, check_can_call
    monkeypatch.setenv("DIALER_TEST_NUMBERS", "+91 79898 22906, 8309831866")
    s = SessionLocal()
    try:
        account = s.get(Account, 1)
        now = datetime(2026, 11, 20, 12, 0, tzinfo=IST).astimezone(timezone.utc)
        tester = Lead(account_id=1, name="Tester", phone_e164="+917989822906", consent_source="test")
        customer = Lead(account_id=1, name="Customer", phone_e164="+919000000777", consent_source="test")
        s.add_all([tester, customer]); s.commit()
        for lead in (tester, customer):  # five answered calls today, the last one ten minutes ago
            for i in range(5):
                s.add(Call(account_id=1, lead_id=lead.id, talk_seconds=60,
                           created_at=(now - timedelta(minutes=10 + i)).replace(tzinfo=None)))
        s.commit()
        account.calling_approved = True
        assert check_can_call(s, account, tester, now).status == "allowed"
        assert check_can_call(s, account, customer, now).status == "deferred"
    finally:
        s.close()


def test_campaign_can_choose_the_engine(monkeypatch):
    from starlette.testclient import TestClient
    from core.auth import create_access_token
    import routers.campaigns as campaigns
    chosen = []
    monkeypatch.setattr("voice_agent.samvaad.set_engine", lambda e: chosen.append(e) or e)
    monkeypatch.setattr(campaigns, "_dialer", lambda: None)

    async def fake_start(**kwargs):
        return True
    monkeypatch.setattr(campaigns.campaign_service, "start_campaign", fake_start)
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + create_access_token(1, 1, "admin@geniusbot.co.in", "owner")
    assert c.post("/api/campaign/start", json={"target": "new", "engine": "pipecat", "consent_confirmed": True}).status_code == 200
    assert chosen == ["pipecat"]
