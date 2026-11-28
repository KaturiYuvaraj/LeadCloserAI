"""
GeniusBot as a platform (28 Nov 2026): one customer must never see another customer's data.

Company A (the seeded account 1) gets records with secret markers. A brand-new company B signs in and
calls every page and every API endpoint of the app. No response may contain A's markers or A's API key.
"""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from core.auth import create_access_token, hash_password
from core.db import SessionLocal
from main import app
from models.account import Account
from models.api_key import ApiKey
from models.billing_order import BillingOrder
from models.call import Call
from models.campaign import Campaign
from models.employee import Employee
from models.lead import Lead
from models.user import User

MARK = "ALPHASECRET" + uuid.uuid4().hex[:6].upper()
A_KEY = "lc_live_" + uuid.uuid4().hex
# not tenant data: public pages, health, docs, webhooks from the phone provider (protected by their own secret)
SKIP_PREFIXES = ("/static", "/docs", "/redoc", "/openapi", "/vobiz", "/telephony/twiml", "/ws", "/health",
                 "/api/tts/demo", "/api/voice/", "/api/auth/logout")


@pytest.fixture(scope="module")
def tenants():
    s = SessionLocal()
    try:
        a = s.get(Account, 1)
        ids = {}
        lead = Lead(account_id=a.id, name=f"{MARK} Lead", phone_e164="+919000011111")
        emp = Employee(account_id=a.id, name=f"{MARK} Employee", greeting=f"{MARK} hello", system_prompt=f"{MARK} prompt")
        camp = Campaign(account_id=a.id, name=f"{MARK} Campaign")
        key = ApiKey(account_id=a.id, key_name=f"{MARK} key", user_email="a@example.com", api_key=A_KEY,
                     company_name=f"{MARK} Co")
        s.add_all([lead, emp, camp, key]); s.flush()
        order = BillingOrder(account_id=a.id, api_key_id=key.id, order_id=f"{MARK}-ORDER",
                             plan_name=f"{MARK} plan", amount_inr=999, minutes_credited=100)
        call = Call(account_id=a.id, lead_id=lead.id, summary=f"{MARK} call summary", transcript=f"{MARK} transcript")
        s.add_all([order, call]); s.flush()
        ids.update(lead=lead.id, employee=emp.id, campaign=camp.id, key=key.id, order=order.id, call=call.id)

        b = Account(name="Bravo Customer Pvt Ltd", calling_approved=False)
        s.add(b); s.flush()
        ub = User(account_id=b.id, email=f"owner-{uuid.uuid4().hex[:6]}@bravo.example", role="owner",
                  password_hash=hash_password("Bravo#2026secure"))
        s.add(ub); s.commit()
        token = create_access_token(user_id=ub.id, account_id=b.id, email=ub.email, role="owner")
        yield {"a_ids": ids, "b_account": b.id, "token": token}
    finally:
        s.close()


PAGES = ["/", "/crm", "/dashboard", "/calling", "/leads", "/campaigns", "/automations", "/analytics", "/login",
         "/set-password"]


def _routes():
    # app.routes hides the included routers here (20 Nov audit), so read them from the OpenAPI schema
    out = [("GET", p) for p in PAGES]
    for path, ops in app.openapi().get("paths", {}).items():
        if path.startswith(SKIP_PREFIXES):
            continue
        for m in ops:
            if m.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                out.append((m.upper(), path))
    assert len(out) > 100, f"only {len(out)} routes found: the test would prove nothing"
    return sorted(set(out))


def _fill(path, ids):
    aliases = {"emp": "employee", "employee": "employee", "lead": "lead", "campaign": "campaign", "key": "key",
               "order": "order", "call": "call"}

    def repl(m):
        name = m.group(1).lower()
        for prefix, kind in aliases.items():
            if name.startswith(prefix):
                return str(ids[kind])
        return str(ids["lead"])
    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", repl, path)


def test_customer_b_never_sees_company_a_data(tenants, monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "true")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {tenants['token']}"}
    client.cookies.set("lc_token", tenants["token"])
    leaks = []
    for method, path in _routes():
        url = _fill(path, tenants["a_ids"])
        try:
            if method == "GET":
                r = client.get(url, headers=headers, follow_redirects=False)
            elif method == "DELETE":
                continue  # deletes are checked separately (they must not touch A's rows)
            else:
                r = client.request(method, url, headers=headers, json={}, follow_redirects=False)
        except Exception as e:  # a crash is not a leak, but report it
            leaks.append(f"{method} {path}: crashed {type(e).__name__}")
            continue
        body = r.text
        if MARK in body or A_KEY in body:
            where = "API KEY" if A_KEY in body else "data"
            leaks.append(f"{method} {path} -> {r.status_code} shows company A {where}")
    assert not leaks, "Company B can see company A:\n" + "\n".join(leaks)


def test_customer_b_cannot_delete_company_a_records(tenants, monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "true")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {tenants['token']}"}
    for method, path in _routes():
        if method != "DELETE":
            continue
        client.delete(_fill(path, tenants["a_ids"]), headers=headers)
    s = SessionLocal()
    try:
        ids = tenants["a_ids"]
        assert s.get(Lead, ids["lead"]) is not None
        assert s.get(Employee, ids["employee"]) is not None
        assert s.get(Campaign, ids["campaign"]) is not None
        assert s.get(ApiKey, ids["key"]) is not None
    finally:
        s.close()


PLATFORM_ONLY = [("GET", "/api/dialer/engine"), ("POST", "/api/dialer/engine"), ("GET", "/api/inbound/hours"),
                 ("POST", "/api/inbound/hours"), ("POST", "/api/dialer/pause"), ("POST", "/api/dialer/resume"),
                 ("POST", "/api/dialer/stop"), ("GET", "/api/integrations/providers"),
                 ("POST", "/api/campaign/start"), ("POST", "/api/campaign/stop"),
                 ("POST", "/api/messaging/whatsapp/send"), ("POST", "/api/calendar/book")]


def test_shared_platform_controls_are_for_the_platform_owner_only(tenants):
    client = TestClient(app)
    customer = {"Authorization": f"Bearer {tenants['token']}"}
    for method, path in PLATFORM_ONLY:
        r = client.request(method, path, headers=customer, json={})
        assert r.status_code == 403, f"customer got {r.status_code} on {method} {path}"
    owner = {"Authorization": "Bearer " + create_access_token(user_id=1, account_id=1, email="admin@geniusbot.co.in",
                                                               role="owner")}
    assert client.get("/api/dialer/engine", headers=owner).status_code == 200


def test_customer_sees_only_its_own_calls_in_the_dialer_status(tenants):
    client = TestClient(app)
    r = client.get("/api/dialer/status", headers={"Authorization": f"Bearer {tenants['token']}"})
    assert r.status_code == 200 and r.json()["events"] == []


def test_new_api_keys_have_no_free_credit_and_stay_in_the_callers_company(tenants):
    client = TestClient(app)
    r = client.post("/api/v1/keys", headers={"Authorization": f"Bearer {tenants['token']}"},
                    json={"key_name": "b key", "account_id": 1, "initial_credits": 99999, "initial_credits_inr": 99999})
    key = r.json()["key"]
    assert key["credits_inr"] == 0
    s = SessionLocal()
    try:
        assert s.get(ApiKey, key["id"]).account_id == tenants["b_account"]
    finally:
        s.close()


def test_purchase_credits_without_payment_is_gone(tenants):
    client = TestClient(app)
    r = client.post("/api/v1/billing/purchase-credits", headers={"Authorization": f"Bearer {tenants['token']}"},
                    json={"amount_inr": 100000})
    assert r.status_code == 410


def test_a_made_up_developer_key_is_refused_everywhere(tenants, monkeypatch):
    """28 Nov: 'Authorization: Bearer lc_live_<anything>' was let through with no company, and the leads,
    calls, employees, campaigns and quotations lists then returned every company's records."""
    monkeypatch.setenv("AUTH_STRICT", "true")
    client = TestClient(app)
    fake = {"Authorization": "Bearer lc_live_made_up_key_0000"}
    for path in ("/api/leads", "/api/calls", "/api/employees", "/api/campaigns", "/api/quotations",
                 "/api/v1/keys", "/api/dialer/jobs"):
        r = client.get(path, headers=fake)
        assert r.status_code == 401, f"{path} answered {r.status_code} to a made-up key"
        assert MARK not in r.text


def test_a_real_developer_key_sees_only_its_own_company(tenants, monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "true")
    client = TestClient(app)
    created = client.post("/api/v1/keys", headers={"Authorization": f"Bearer {tenants['token']}"},
                          json={"key_name": "b integration"}).json()["key"]["api_key"]
    r = client.get("/api/leads", headers={"Authorization": f"Bearer {created}"})
    assert r.status_code == 200 and MARK not in r.text


def test_production_is_always_strict(monkeypatch):
    monkeypatch.setenv("AUTH_STRICT", "false")
    monkeypatch.setenv("APP_ENV", "production")
    assert TestClient(app).get("/api/leads").status_code == 401
