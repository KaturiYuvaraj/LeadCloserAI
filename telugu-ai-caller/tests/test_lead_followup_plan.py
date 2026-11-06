"""
Unit and integration tests for Task Y4:
Show each lead's follow-up plan (Next AI call, smart cadence stage, or stopped/with sales team)
and pending WhatsApp badges.
"""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token
from core.db import SessionLocal
from models import Lead, Call, User, Account
from services.followup_engine import compute_next_followup_step


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_followup_leads():
    session = SessionLocal()
    try:
        phones = ["+919876543301", "+919876543302", "+919876543303"]
        session.query(Lead).filter(Lead.phone_e164.in_(phones)).delete(synchronize_session=False)
        session.commit()

        leads = [
            Lead(
                name="Cadence Lead",
                company="Cadence Enterprises",
                phone="+919876543301",
                phone_e164="+919876543301",
                account_id=1,
                last_outcome="interested_later",
                variables={
                    "status": "FOLLOW_UP",
                    "followup_plan": {
                        "should_followup": True,
                        "stage": "days_1_to_3",
                        "channel": "ai_call",
                        "next_action_at": "2026-11-07T10:30:00+05:30",
                        "reason": "Smart cadence Days 1–3: daily rotating morning call"
                    },
                    "pending_whatsapp": [
                        {"what": "website catalog", "at": "2026-11-06 10:30 IST"},
                        {"what": "pricing pdf", "at": "2026-11-06 10:31 IST"}
                    ]
                }
            ),
            Lead(
                name="Sales Team Lead",
                company="Hot Deal Inc",
                phone="+919876543302",
                phone_e164="+919876543302",
                account_id=1,
                is_hot=True,
                last_outcome="demo_booked",
                variables={
                    "status": "DEMO_BOOKED",
                    "followup_plan": {
                        "should_followup": False,
                        "stage": "with_sales_team",
                        "channel": "human",
                        "next_action_at": None,
                        "reason": "Demo booked; handed off to sales team"
                    }
                }
            ),
            Lead(
                name="Opted Out Lead",
                company="Do Not Call Corp",
                phone="+919876543303",
                phone_e164="+919876543303",
                account_id=1,
                opt_out=True,
                last_outcome="do_not_call",
                variables={
                    "status": "CLOSED_LOST",
                    "followup_plan": {
                        "should_followup": False,
                        "stage": "stopped_opt_out",
                        "channel": "none",
                        "next_action_at": None,
                        "reason": "Lead opted out"
                    }
                }
            )
        ]
        session.add_all(leads)
        session.commit()
    finally:
        session.close()


def test_lead_followup_plan_rendered_in_crm_table(client, auth_headers, seed_followup_leads):
    """CRM page renders next AI call schedule, with sales team, stopped, and WhatsApp queued badge."""
    resp = client.get("/crm", headers=auth_headers)
    assert resp.status_code == 200
    html = resp.text

    # Next AI call
    assert "Next AI call:" in html
    assert "WhatsApp queued (2)" in html

    # With sales team
    assert "With sales team" in html

    # Stopped: Do-Not-Call
    assert "Stopped: Do-Not-Call" in html


def test_business_intel_modal_has_followup_card(client, auth_headers):
    """Business Intel dossier contains the follow-up plan elements."""
    resp = client.get("/crm", headers=auth_headers)
    assert resp.status_code == 200
    html = resp.text

    assert "intelFollowupCard" in html
    assert "intelFollowupPlanText" in html
    assert "intelFollowupReason" in html
    assert "intelWhatsAppBadge" in html


def test_api_leads_returns_variables_with_followup_plan(client, auth_headers, seed_followup_leads):
    """GET /api/leads exposes variables containing followup_plan and pending_whatsapp for frontend rendering."""
    resp = client.get("/api/leads", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    leads = data.get("leads", [])

    cadence_lead = next((l for l in leads if l.get("phone") == "+919876543301"), None)
    assert cadence_lead is not None
    vars_dict = cadence_lead.get("variables", {})
    assert "followup_plan" in vars_dict
    assert vars_dict["followup_plan"]["stage"] == "days_1_to_3"
    assert len(vars_dict["pending_whatsapp"]) == 2
