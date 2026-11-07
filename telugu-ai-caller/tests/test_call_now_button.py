"""
The admin's "Call now" button (routers/dialer.py: preflight check + call-now).
Offline: the stub dialer and fixed clock (Monday 2 Nov 2026, 11:00 IST) come from tests/test_dialer.py;
nothing is dialled and Sarvam is not contacted.
"""

from datetime import timedelta

import pytest
from starlette.testclient import TestClient

import main
import routers.dialer as dialer_router
from core.auth import create_access_token
from core.db import SessionLocal
from models import Account, Call, CallJob, Lead, User
from tests.test_dialer import MONDAY_11_IST, job_for, make_lead, queue  # noqa: F401  (fixture)
from voice_agent import credits
from voice_agent import dialer as dialer_module


@pytest.fixture
def api(queue, monkeypatch):
    """A signed-in owner of account 1, talking to the test queue (stub dialer, fixed clock)."""
    monkeypatch.setattr(dialer_router, "call_queue", queue)
    monkeypatch.setattr(queue, "start", lambda: None)
    credits.clear("test")
    client = TestClient(main.app)
    client.headers["Authorization"] = "Bearer " + create_access_token(1, 1, "admin@leadcloser.ai", "owner")
    yield client
    credits.clear("test")


def job_count(lead_id):
    session = SessionLocal()
    try:
        return session.query(CallJob).filter(CallJob.lead_id == lead_id).count()
    finally:
        session.close()


def lead_row(lead_id):
    session = SessionLocal()
    try:
        return session.get(Lead, lead_id)
    finally:
        session.close()


def test_login_is_required(queue, monkeypatch):
    monkeypatch.setattr(dialer_router, "call_queue", queue)
    lead = make_lead(name="Anon Anil", phone="+919812300801")
    stranger = TestClient(main.app)
    assert stranger.post(f"/api/dialer/call-now/{lead}", json={}).status_code == 401
    assert stranger.get(f"/api/dialer/call-now/{lead}/check").status_code == 401
    assert queue.dialer.dialed == []


def test_other_companies_leads_are_not_found(api):
    session = SessionLocal()
    other = Account(name="Other Co", calling_approved=True)
    session.add(other)
    session.commit()
    lead = Lead(account_id=other.id, name="Secret Sam", phone_e164="+919812300802", consent_source="test")
    session.add(lead)
    session.commit()
    lead_id = lead.id
    session.close()
    assert api.post(f"/api/dialer/call-now/{lead_id}", json={"consent_confirmed": True}).status_code == 404
    assert api.get(f"/api/dialer/call-now/{lead_id}/check").status_code == 404
    assert api.get("/api/dialer/call-now/999999/check").status_code == 404


def test_check_changes_nothing(api, queue):
    lead = make_lead(name="Check Chandra", phone="+919812300803", source="csv_import", consent=False)
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["status"] == "blocked" and check["needs_consent"] and check["can_call"] is False
    session = SessionLocal()
    assert session.query(CallJob).filter(CallJob.lead_id == lead).count() == 0
    assert session.get(Lead, lead).consent_source is None
    session.close()


def test_call_goes_through_the_dialer_and_returns_a_job(api, queue):
    lead = make_lead(name="Happy Hari", phone="+919812300804")
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["status"] == "allowed" and check["can_call"] and not check["outside_calling_hours"]
    result = api.post(f"/api/dialer/call-now/{lead}", json={}).json()
    assert result["success"] and result["status"] == "queued" and result["job_id"] == job_for(lead).id
    assert job_for(lead).priority == 0 and job_for(lead).state == "queued"


@pytest.mark.asyncio
async def test_the_call_is_actually_dialled(api, queue):
    lead = make_lead(name="Dial Deepak", phone="+919812300805")
    assert api.post(f"/api/dialer/call-now/{lead}", json={}).json()["success"]
    await queue.tick()
    assert len(queue.dialer.dialed) == 1 and job_for(lead).state == "dialing"


def test_no_consent_needs_the_admins_explicit_confirmation(api, queue):
    lead = make_lead(name="Consent Chaitra", phone="+919812300806", source="csv_import", consent=False)
    refused = api.post(f"/api/dialer/call-now/{lead}", json={}).json()
    assert refused["success"] is False and refused["needs_consent"] and job_count(lead) == 0
    assert lead_row(lead).consent_source is None
    done = api.post(f"/api/dialer/call-now/{lead}", json={"consent_confirmed": True}).json()
    assert done["success"] and done["status"] == "queued"
    # the consent record names who confirmed it, not a made-up campaign
    assert lead_row(lead).consent_source.startswith("confirmed_by admin@leadcloser.ai ")


def test_opted_out_lead_is_never_called(api, queue):
    lead = make_lead(name="Optout Om", phone="+919812300807", opt_out=True)
    result = api.post(f"/api/dialer/call-now/{lead}", json={"consent_confirmed": True}).json()
    assert result["success"] is False and result["status"] == "blocked" and result["reason"] == "opted_out"
    assert "Do-Not-Call" in result["message"] and job_count(lead) == 0


def test_invalid_number_is_refused(api, queue):
    lead = make_lead(name="Short Sita", phone="+9112345")
    assert api.post(f"/api/dialer/call-now/{lead}", json={"consent_confirmed": True}).json()["reason"] == "invalid_number"


def test_credits_finished_stops_the_button(api, queue):
    lead = make_lead(name="Credit Chitti", phone="+919812300808")
    credits.report_error('{"error":{"message":"No credits available."}}', "test")
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["status"] == "service_unavailable" and "Sarvam credits finished" in check["message"]
    assert api.post(f"/api/dialer/call-now/{lead}", json={}).json()["success"] is False and job_count(lead) == 0


def test_paused_dialer_stops_the_button(api, queue):
    lead = make_lead(name="Paused Pavan", phone="+919812300809")
    queue.paused = True
    try:
        assert api.post(f"/api/dialer/call-now/{lead}", json={}).json()["status"] == "paused"
    finally:
        queue.paused = False


def test_weekly_limit_asks_to_schedule_instead_of_calling(api, queue):
    lead = make_lead(name="Weekly Wasim", phone="+919812300810")
    session = SessionLocal()
    for days_ago in (1, 2, 3, 4):
        session.add(Call(account_id=1, lead_id=lead, talk_seconds=30, created_at=MONDAY_11_IST - timedelta(days=days_ago)))
    session.commit()
    session.close()
    first = api.post(f"/api/dialer/call-now/{lead}", json={}).json()
    assert first["success"] is False and first["status"] == "deferred" and first["reason"] == "weekly_limit"
    assert first["can_schedule"] and first["next_allowed_at"] and job_count(lead) == 0
    scheduled = api.post(f"/api/dialer/call-now/{lead}", json={"schedule": True}).json()
    assert scheduled["success"] and scheduled["status"] == "scheduled" and job_count(lead) == 1


def test_recent_call_is_a_warning_not_a_block(api, queue):
    # a person pressing the button may call again within 24 h; the page warns using last_called_hours_ago
    lead = make_lead(name="Recent Rani", phone="+919812300811")
    session = SessionLocal()
    session.add(Call(account_id=1, lead_id=lead, talk_seconds=40, created_at=MONDAY_11_IST - timedelta(hours=3)))
    session.commit()
    session.close()
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["can_call"] and check["last_called_hours_ago"] == 3.0
    assert api.post(f"/api/dialer/call-now/{lead}", json={}).json()["success"]


def test_outside_calling_hours_is_flagged_for_a_warning(api, queue, monkeypatch):
    lead = make_lead(name="Night Nikhil", phone="+919812300812")
    monkeypatch.setattr(dialer_module, "utcnow", lambda: MONDAY_11_IST.replace(hour=17))  # 22:30 IST
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["can_call"] and check["outside_calling_hours"]


def test_pressing_twice_does_not_duplicate_the_call(api, queue):
    lead = make_lead(name="Twice Tara", phone="+919812300813")
    api.post(f"/api/dialer/call-now/{lead}", json={})
    api.post(f"/api/dialer/call-now/{lead}", json={})
    session = SessionLocal()
    assert session.query(CallJob).filter(CallJob.lead_id == lead).count() == 1
    session.close()


@pytest.mark.asyncio
async def test_pressing_during_a_live_call_does_not_queue_another(api, queue):
    lead = make_lead(name="Live Lalitha", phone="+919812300814")
    api.post(f"/api/dialer/call-now/{lead}", json={})
    await queue.tick()
    queue.on_answered(job_for(lead).id)
    again = api.post(f"/api/dialer/call-now/{lead}", json={}).json()
    assert again["success"] and again["status"] == "in_progress" and len(queue.dialer.dialed) == 1


def test_jobs_list_only_shows_the_signed_in_companys_jobs(api, queue):
    lead = make_lead(name="Mine Mani", phone="+919812300815")
    api.post(f"/api/dialer/call-now/{lead}", json={})
    jobs = api.get(f"/api/dialer/jobs?lead_id={lead}&limit=1").json()["jobs"]
    assert jobs and jobs[0]["lead_id"] == lead
    session = SessionLocal()
    other = Account(name="Jobs Other Co", calling_approved=True)
    session.add(other)
    session.commit()
    stranger = User(id=9001, account_id=other.id, email="jobs.other@example.com", password_hash="x", role="owner")
    session.add(stranger)
    session.commit()
    api.headers["Authorization"] = "Bearer " + create_access_token(stranger.id, other.id, stranger.email, "owner")
    session.close()
    assert api.get(f"/api/dialer/jobs?lead_id={lead}&limit=1").json()["jobs"] == []


def test_legacy_outbound_route_needs_login_and_a_lead_when_vobiz_is_the_phone_line(queue, monkeypatch):
    monkeypatch.setattr(dialer_router, "call_queue", queue)
    monkeypatch.setenv("DIALER_PROVIDER", "vobiz")
    client = TestClient(main.app)
    assert client.post("/api/call/outbound", json={"phone": "+919812300816"}).status_code == 401
    client.headers["Authorization"] = "Bearer " + create_access_token(1, 1, "admin@leadcloser.ai", "owner")
    # no lead_id: it must not turn a raw number into a lead and dial it
    assert client.post("/api/call/outbound", json={"phone": "+919812300816"}).status_code == 400
    session = SessionLocal()
    assert session.query(Lead).filter(Lead.phone_e164 == "+919812300816").count() == 0
    session.close()
    assert queue.dialer.dialed == []
