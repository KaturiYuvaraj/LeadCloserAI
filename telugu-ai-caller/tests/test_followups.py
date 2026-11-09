"""
Tests for follow-ups (voice_agent/followups.py): the follow-up engine's plan becomes dialer jobs.
Offline: the stub dialer and fixed clock come from tests/test_dialer.py.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.db import SessionLocal
from models import Call, CallJob, Lead
from tests.test_dialer import MONDAY_11_IST, ist, job_for, make_lead, queue  # noqa: F401  (fixture)
from voice_agent import dialer as dialer_module
from voice_agent import followups


def set_outcome(lead_id, label, **extra):
    session = SessionLocal()
    lead = session.get(Lead, lead_id)
    lead.variables = {**(lead.variables or {}), "outcome_label": label, **extra}
    session.commit()
    session.close()


def lead_vars(lead_id):
    session = SessionLocal()
    try:
        return dict(session.get(Lead, lead_id).variables or {})
    finally:
        session.close()


def waiting_jobs(lead_id):
    session = SessionLocal()
    try:
        return session.query(CallJob).filter(
            CallJob.lead_id == lead_id, CallJob.state.in_(followups.WAITING_STATES)).all()
    finally:
        session.close()


async def answered_call(queue, lead_id, outcome):
    """Dial the lead, the lead answers, the engine saves the call with `outcome`."""
    queue.enqueue([lead_id])
    await queue.tick()
    job = job_for(lead_id)
    queue.on_answered(job.id)
    queue.on_call_saved(job.id, None, outcome)
    return job


@pytest.mark.asyncio
async def test_busy_lead_gets_next_day_cadence_call(queue):
    lead = make_lead(name="Busy Bhanu", phone="+919812300201")
    set_outcome(lead, "busy_no_time")
    first = await answered_call(queue, lead, "follow_up")
    job = job_for(lead)
    assert job.id != first.id and job.state == "scheduled" and job.last_disposition == "followup"
    # days 1–3: once a day at a rotating time → tomorrow 10:30 IST
    assert job.next_attempt_at.replace(tzinfo=timezone.utc) == ist(10, 30, day=3)
    assert lead_vars(lead)["followup_plan"]["stage"] == "days_1_to_3"


@pytest.mark.asyncio
async def test_requested_callback_time_is_kept(queue):
    lead = make_lead(name="Later Lakshmi", phone="+919812300202")
    set_outcome(lead, "callback_scheduled", callback_at="2026-11-05 17:30")
    await answered_call(queue, lead, "follow_up")
    job = job_for(lead)
    assert job.last_disposition == "callback_requested" and job.priority == 1
    assert job.next_attempt_at.replace(tzinfo=timezone.utc) == ist(17, 30, day=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("label,stage", [("meeting_booked", "with_sales_team"), ("not_interested", "closed")])
async def test_hot_and_closed_leads_get_no_ai_calls(queue, label, stage):
    lead = make_lead(name=f"Done {label}", phone=f"+91981230021{len(label) % 10}")
    set_outcome(lead, label)
    await answered_call(queue, lead, label)
    assert waiting_jobs(lead) == []
    assert lead_vars(lead)["followup_plan"]["stage"] == stage


@pytest.mark.asyncio
async def test_callback_booked_during_the_call_wins(queue):
    lead = make_lead(name="Marker Mani", phone="+919812300203")
    set_outcome(lead, "busy_no_time")
    queue.enqueue([lead])
    await queue.tick()
    job = job_for(lead)
    queue.on_answered(job.id)
    session = SessionLocal()  # what [CALLBACK: …] does mid-call (voice_agent/actions.py)
    session.add(CallJob(account_id=1, lead_id=lead, phone_e164="+919812300203", provider="pending",
                        state="scheduled", priority=1, attempt=0, max_attempts=2,
                        next_attempt_at=ist(16, 0, day=3), last_disposition="callback_requested"))
    session.commit()
    session.close()
    queue.on_call_saved(job.id, None, "follow_up")
    jobs = waiting_jobs(lead)
    assert len(jobs) == 1 and jobs[0].last_disposition == "callback_requested"


@pytest.mark.asyncio
async def test_unreachable_lead_gets_one_missed_call_whatsapp_then_cadence(queue, monkeypatch):
    lead = make_lead(name="Silent Sita", phone="+919812300204")
    queue.enqueue([lead], max_attempts=1)
    await queue.tick()
    queue.on_provider_hangup(job_for(lead).id, "no-answer", 0, "NO_ANSWER")
    cadence = job_for(lead)
    assert cadence.state == "scheduled" and cadence.last_disposition == "followup"
    assert cadence.next_attempt_at.replace(tzinfo=timezone.utc) > MONDAY_11_IST + timedelta(days=1)
    assert [w["what"] for w in lead_vars(lead)["pending_whatsapp"]] == [followups.MISSED_CALL_WHATSAPP]

    # the cadence call is not answered either: next cadence step, but no second missed-call WhatsApp
    monkeypatch.setattr(dialer_module, "utcnow", lambda: cadence.next_attempt_at.replace(tzinfo=timezone.utc))
    await queue.tick()
    assert job_for(lead).state == "dialing"
    queue.on_provider_hangup(cadence.id, "no-answer", 0, "NO_ANSWER")
    assert job_for(lead).id != cadence.id and job_for(lead).state == "scheduled"
    assert len(lead_vars(lead)["pending_whatsapp"]) == 1


def test_after_day_30_whatsapp_first_and_no_call(queue):
    lead = make_lead(name="Old Obul", phone="+919812300205")
    set_outcome(lead, "busy_no_time")
    session = SessionLocal()
    session.add(Call(account_id=1, lead_id=lead, talk_seconds=60, created_at=MONDAY_11_IST - timedelta(days=40)))
    session.commit()
    job = CallJob(account_id=1, lead_id=lead, phone_e164="+919812300205", state="completed")
    session.add(job)
    session.commit()
    assert followups.after_conversation(session, job, "follow_up", MONDAY_11_IST) is None
    session.commit()
    session.close()
    assert waiting_jobs(lead) == []
    assert lead_vars(lead)["followup_plan"]["channel"] == "whatsapp_first"
    assert lead_vars(lead)["pending_whatsapp"][-1]["what"] == "follow-up nudge"


@pytest.mark.asyncio
async def test_cadence_call_is_not_held_back_by_called_recently(queue, monkeypatch):
    lead = make_lead(name="Cadence Chandu", phone="+919812300206")
    set_outcome(lead, "busy_no_time")
    await answered_call(queue, lead, "follow_up")
    session = SessionLocal()  # the call record the engine saves
    session.add(Call(account_id=1, lead_id=lead, talk_seconds=90, created_at=MONDAY_11_IST))
    session.commit()
    session.close()
    follow_up = job_for(lead)
    due = follow_up.next_attempt_at.replace(tzinfo=timezone.utc)
    assert due - MONDAY_11_IST < timedelta(hours=24)  # tomorrow 10:30, inside the 24 h "recently" window
    monkeypatch.setattr(dialer_module, "utcnow", lambda: due)
    await queue.tick()
    assert job_for(lead).state == "dialing"


def test_unanswered_calls_are_retried_30_to_45_minutes_later_up_to_5_times():
    for attempt in range(1, 6):
        gap = followups.retry_time(attempt, MONDAY_11_IST) - MONDAY_11_IST
        assert timedelta(minutes=30) <= gap <= timedelta(minutes=45)
    assert followups.MAX_ATTEMPTS == 5
