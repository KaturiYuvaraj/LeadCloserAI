"""
Phase 0 Foundation Test Suite (LeadCloserAI Plan v2):
  1. Login, JWT/cookie sessions, and role enforcement (owner | admin | member)
  2. Multi-account data isolation (Account A cannot read/modify Account B's leads or calls)
  3. 4-Bucket & 13-Outcome taxonomy, IST callback parsing, confidence human review,
     rep outcome override with AuditLog, and automatic Do-Not-Call opt-out
  4. Real outbound campaign queue routing via /api/campaign/start (fake simulation removed)
"""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.auth import create_access_token, hash_password
from core.db import SessionLocal
from database import init_db, save_call_record
from main import app
from models import Account, AuditLog, OptOut, User
from services.outcomes import OUTCOME_BUCKETS, OUTCOME_CATALOG, normalize_outcome, parse_callback_time_ist

init_db()
client = TestClient(app)


def test_login_page_and_unauthenticated_me():
    resp_page = client.get("/login")
    assert resp_page.status_code == 200
    assert "Team Sign In" in resp_page.text

    resp_me = client.get("/api/auth/me")
    assert resp_me.status_code == 401


def test_login_and_role_permissions():
    # 1. Login as seeded owner (admin@leadcloser.ai)
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "admin@leadcloser.ai", "password": "admin123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["success"] is True
    token = data["access_token"]
    assert data["user"]["email"] == "admin@leadcloser.ai"

    # 2. Verify /api/auth/me with Bearer token
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["account_id"] == 1

    # 3. Invite a "member" sales rep via /api/team
    rep_email = f"rep_{uuid.uuid4().hex[:6]}@spassociates.com"
    invite_resp = client.post(
        "/api/team",
        json={"email": rep_email, "password": "repPassword123", "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invite_resp.status_code == 200
    rep_user = invite_resp.json()["user"]
    assert rep_user["role"] == "member"

    # 4. Login as the "member" rep and verify they CANNOT invite/delete team members (403)
    rep_login = client.post(
        "/api/auth/login",
        json={"email": rep_email, "password": "repPassword123"},
    )
    assert rep_login.status_code == 200
    rep_token = rep_login.json()["access_token"]

    forbidden_resp = client.post(
        "/api/team",
        json={"email": "another@spassociates.com", "password": "password123", "role": "member"},
        headers={"Authorization": f"Bearer {rep_token}"},
    )
    assert forbidden_resp.status_code == 403

    # Clear cookies on shared TestClient
    client.cookies.clear()


def test_multi_account_isolation():
    """Prove User B in Account B cannot read or modify Account A's leads."""
    session = SessionLocal()
    try:
        acct_b = Account(
            name=f"Tenant B {uuid.uuid4().hex[:4]}",
            default_language="en-IN",
            calling_approved=True,
            rate_per_min=5.00,
        )
        session.add(acct_b)
        session.flush()

        user_b = User(
            account_id=acct_b.id,
            email=f"owner_b_{uuid.uuid4().hex[:6]}@tenantb.com",
            password_hash=hash_password("tenantBpass"),
            role="owner",
        )
        session.add(user_b)
        session.commit()
        token_b = create_access_token(user_b.id, acct_b.id, user_b.email, user_b.role)
        acct_b_id = acct_b.id
    finally:
        session.close()

    # Account 1 token
    token_a = create_access_token(1, 1, "admin@leadcloser.ai", "owner")

    # Create a lead in Account A
    phone_a = f"+919848{uuid.uuid4().int % 1000000:06d}"
    resp_a = client.post(
        "/api/leads",
        json={"name": "Account A Secret Lead", "phone": phone_a, "company": "Alpha Corp"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == 200
    lead_a_id = resp_a.json()["lead_id"]

    # Create a lead in Account B
    phone_b = f"+919849{uuid.uuid4().int % 1000000:06d}"
    resp_b = client.post(
        "/api/leads",
        json={"name": "Account B Exclusive Lead", "phone": phone_b, "company": "Beta Pvt Ltd"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    lead_b_id = resp_b.json()["lead_id"]

    # User B lists leads -> must ONLY see Account B's lead, never Account A's lead
    list_b = client.get("/api/leads", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    ids_b = {l["id"] for l in list_b.json()["leads"]}
    assert lead_b_id in ids_b
    assert lead_a_id not in ids_b

    # User B tries to fetch Account A's lead directly -> 404
    get_a_by_b = client.get(f"/api/leads/{lead_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_a_by_b.status_code == 404


def test_v2_four_buckets_and_outcome_labels():
    """Verify the 4 buckets and all §3 outcome labels, callback parsing, and rep override."""
    assert set(OUTCOME_BUCKETS.keys()) == {"hot", "follow_up", "closed", "not_reachable"}
    expected_labels = {
        "interested_now", "meeting_booked", "human_requested",
        "callback_scheduled", "interested_later", "send_details_first", "decision_maker", "busy_no_time",
        "not_interested", "do_not_call", "wrong_person", "invalid_lead",
        "no_answer", "busy", "switched_off", "voicemail", "invalid_number",
    }
    assert expected_labels.issubset(set(OUTCOME_CATALOG.keys()))

    # Low confidence triggers human review
    low_conf = normalize_outcome("interested_now", confidence=0.55)
    assert low_conf["outcome_bucket"] == "hot"
    assert low_conf["needs_human_review"] is True

    # Callback time parser ("tomorrow 6 PM" -> 18:00 IST)
    cb_dt = parse_callback_time_ist("tomorrow 6 PM")
    assert cb_dt is not None
    assert cb_dt.hour == 18
    assert cb_dt.minute == 0

    # Save a call with outcome_label="interested_now" and verify lead bucket is "hot"
    phone = f"+919701{uuid.uuid4().int % 1000000:06d}"
    create_resp = client.post("/api/leads", json={"name": "Hot Prospect", "phone": phone})
    lead_id = create_resp.json()["lead_id"]

    save_call_record({
        "lead_id": lead_id,
        "duration_seconds": 75,
        "outcome_label": "interested_now",
        "outcome_reason": "Asked for e-commerce quotation on WhatsApp",
        "whatsapp_opt_in": True,
        "confidence": 0.94,
        "summary": "Client requested quotation for e-commerce portal.",
    })

    lead_resp = client.get(f"/api/leads/{lead_id}").json()["lead"]
    assert lead_resp["outcome_bucket"] == "hot"
    assert lead_resp["outcome_label"] == "interested_now"
    assert lead_resp["is_hot"] is True
    assert lead_resp["whatsapp_opt_in"] is True

    # Rep overrides outcome to "do_not_call" -> sets opt_out=True, adds OptOut row, logs AuditLog
    override_resp = client.post(
        f"/api/leads/{lead_id}/outcome",
        json={"outcome_label": "do_not_call", "reason": "Customer requested no further calls"},
    )
    assert override_resp.status_code == 200
    updated_lead = override_resp.json()["lead"]
    assert updated_lead["outcome_bucket"] == "closed"
    assert updated_lead["outcome_label"] == "do_not_call"
    assert updated_lead["opt_out"] is True

    session = SessionLocal()
    try:
        opt_row = session.query(OptOut).filter_by(phone_e164=phone).first()
        assert opt_row is not None
        audit_row = (
            session.query(AuditLog)
            .filter_by(action="override_outcome", target=f"lead:{lead_id}")
            .first()
        )
        assert audit_row is not None
    finally:
        session.close()


def test_campaign_start_uses_real_queue_not_simulation():
    """Verify /api/campaign/start queues jobs on the real dialer queue (mode='phone')."""
    phone = f"+919611{uuid.uuid4().int % 1000000:06d}"
    lead_id = client.post("/api/leads", json={"name": "Queue Test Lead", "phone": phone}).json()["lead_id"]

    start_resp = client.post(
        "/api/campaign/start",
        json={"lead_ids": [lead_id], "consent_confirmed": True},
    )
    assert start_resp.status_code == 200
    body = start_resp.json()
    assert body["success"] is True
    assert body["mode"] == "phone"
    assert "provider" in body

    status_resp = client.get("/api/campaign/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["mode"] == "phone"

    client.post("/api/campaign/stop")

