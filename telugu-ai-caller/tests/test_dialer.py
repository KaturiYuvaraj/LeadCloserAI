"""
Tests for the outbound dialer (Phase 0): calling rules and the call queue.
Offline: a recording stub replaces the phone provider; the clock is fixed.
"""

from datetime import datetime, time, timedelta, timezone

import pytest

from core.db import SessionLocal
from database import create_lead
from models import Account, CallJob, Lead, OptOut
from voice_agent import dialer as dialer_module
from voice_agent.dialer import CallQueue
from voice_agent.rules import IST, check_can_call, is_dialable_number, next_window_start

# Monday 2 Nov 2026, 11:00 IST: inside the default 9:00–19:00 window
MONDAY_11_IST = datetime(2026, 11, 2, 11, 0, tzinfo=IST).astimezone(timezone.utc)


def ist(hour, minute=0, day=2):
    return datetime(2026, 11, day, hour, minute, tzinfo=IST).astimezone(timezone.utc)


def make_lead(name="Rule Test", phone="+919812300001", source="manual", consent=True, opt_out=False):
    lead_id = create_lead({"name": name, "phone": phone, "service_needed": "Website"})
    session = SessionLocal()
    lead = session.get(Lead, lead_id)
    lead.source = source
    lead.consent_source = "test" if consent else None
    lead.opt_out = opt_out
    session.commit()
    session.close()
    return lead_id


def account_and_lead(lead_id):
    session = SessionLocal()
    account = session.get(Account, 1)
    account.calling_approved = True
    account.calling_start, account.calling_end = time(9, 0), time(19, 0)
    account.calling_days = list(range(7))
    account.recent_call_hours = 24
    session.commit()
    return session, account, session.get(Lead, lead_id)


# ---------------------------------------------------------------------------- rules

@pytest.mark.parametrize("phone,ok", [
    ("+919876543210", True), ("+914023456789", True), ("+91123", False),
    ("9876543210", False), ("+15551234567", True), ("", False),
])
def test_dialable_numbers(phone, ok):
    assert is_dialable_number(phone) is ok


def test_rules_allow_inside_window():
    session, account, lead = account_and_lead(make_lead(phone="+919812300011"))
    assert check_can_call(session, account, lead, MONDAY_11_IST).status == "allowed"
    session.close()


def test_rules_defer_outside_hours_to_next_morning():
    session, account, lead = account_and_lead(make_lead(phone="+919812300012"))
    result = check_can_call(session, account, lead, ist(20, 30))
    assert result.status == "deferred" and result.reason == "outside_calling_hours"
    assert result.next_allowed_at == ist(9, 0, day=3)
    early = check_can_call(session, account, lead, ist(7, 0))
    assert early.next_allowed_at == ist(9, 0)
    session.close()


def test_account_window_is_clamped_to_legal_9_to_9():
    session, account, lead = account_and_lead(make_lead(phone="+919812300013"))
    account.calling_start, account.calling_end = time(6, 0), time(23, 0)
    assert check_can_call(session, account, lead, ist(8, 0)).reason == "outside_calling_hours"
    assert check_can_call(session, account, lead, ist(21, 30)).reason == "outside_calling_hours"
    assert check_can_call(session, account, lead, ist(20, 30)).status == "allowed"
    session.close()


def test_blocked_days_skip_to_next_allowed_day():
    session, account, lead = account_and_lead(make_lead(phone="+919812300014"))
    account.calling_days = [0, 1, 2, 3, 4, 5]  # no Sundays; 8 Nov 2026 is a Sunday
    result = check_can_call(session, account, lead, ist(11, 0, day=8))
    assert result.status == "deferred" and result.next_allowed_at == ist(9, 0, day=9)
    session.close()


@pytest.mark.parametrize("kwargs,reason", [
    ({"opt_out": True}, "opted_out"),
    ({"phone": "+91555"}, "invalid_number"),
    ({"source": "csv", "consent": False}, "no_consent"),
])
def test_rules_block(kwargs, reason):
    defaults = {"phone": f"+9198123{abs(hash(reason)) % 100000:05d}"}
    session, account, lead = account_and_lead(make_lead(**{**defaults, **kwargs}))
    result = check_can_call(session, account, lead, MONDAY_11_IST)
    assert result.status == "blocked" and result.reason == reason
    session.close()


def test_opt_out_list_blocks_even_if_lead_flag_is_off():
    lead_id = make_lead(phone="+919812300016")
    session, account, lead = account_and_lead(lead_id)
    session.add(OptOut(account_id=1, phone_e164=lead.phone_e164, reason="asked on call"))
    session.commit()
    assert check_can_call(session, account, lead, MONDAY_11_IST).reason == "opted_out"
    session.close()


def test_self_initiated_sources_need_no_consent_tick():
    session, account, lead = account_and_lead(make_lead(phone="+919812300017", source="webform", consent=False))
    assert check_can_call(session, account, lead, MONDAY_11_IST).status == "allowed"
    session.close()


def test_account_not_approved_blocks():
    session, account, lead = account_and_lead(make_lead(phone="+919812300018"))
    account.calling_approved = False
    assert check_can_call(session, account, lead, MONDAY_11_IST).reason == "account_not_approved"
    account.calling_approved = True
    session.commit()
    session.close()


def test_next_window_start_inside_window_is_now():
    session = SessionLocal()
    account = session.get(Account, 1)
    account.calling_start, account.calling_end, account.calling_days = time(9, 0), time(19, 0), list(range(7))
    assert next_window_start(MONDAY_11_IST, account) == MONDAY_11_IST
    session.close()


# ---------------------------------------------------------------------------- queue

class StubDialer:
    name = "stub"

    def __init__(self):
        self.dialed = []

    def is_configured(self):
        return True

    async def dial(self, req):
        self.dialed.append(req)
        return f"stub-{req.job_id}"


@pytest.fixture
def queue(monkeypatch):
    monkeypatch.setattr(dialer_module, "utcnow", lambda: MONDAY_11_IST)
    q = CallQueue()
    q.dialer = StubDialer()
    q.max_lines = 2
    session = SessionLocal()
    account = session.get(Account, 1)
    account.calling_approved = True
    account.calling_start, account.calling_end, account.calling_days = time(9, 0), time(19, 0), list(range(7))
    session.query(CallJob).delete()
    session.commit()
    session.close()
    return q


def job_for(lead_id):
    session = SessionLocal()
    try:
        job = session.query(CallJob).filter(CallJob.lead_id == lead_id).order_by(CallJob.id.desc()).first()
        session.expunge(job)
        return job
    finally:
        session.close()


@pytest.mark.asyncio
async def test_queue_dials_up_to_free_lines_and_skips_duplicates(queue):
    leads = [make_lead(name=f"Q{i}", phone=f"+91981230010{i}") for i in range(3)]
    assert queue.enqueue(leads)["queued"] == 3
    assert queue.enqueue(leads)["already_queued"] == 3
    await queue.tick()
    assert len(queue.dialer.dialed) == 2  # only 2 lines
    await queue.tick()
    assert len(queue.dialer.dialed) == 2  # still busy
    queue.on_answered(job_for(leads[0]).id)
    queue.on_call_saved(job_for(leads[0]).id, None, "demo_scheduled")
    await queue.tick()
    assert len(queue.dialer.dialed) == 3  # a line freed up
    assert job_for(leads[0]).state == "completed"
    assert job_for(leads[0]).last_disposition == "demo_scheduled"


@pytest.mark.asyncio
async def test_no_answer_retries_then_not_reachable(queue, monkeypatch):
    lead = make_lead(name="Retry Rao", phone="+919812300120")
    queue.enqueue([lead], max_attempts=2)
    await queue.tick()
    job = job_for(lead)
    assert job.state == "dialing" and job.attempt == 1

    queue.on_provider_hangup(job.id, "no-answer", 0, "NO_ANSWER")
    job = job_for(lead)
    assert job.state == "retry_scheduled" and job.last_disposition == "no_answer"

    # move the clock past the retry time and dial again
    monkeypatch.setattr(dialer_module, "utcnow", lambda: MONDAY_11_IST + timedelta(hours=3))
    await queue.tick()
    job = job_for(lead)
    assert job.state == "dialing" and job.attempt == 2

    queue.on_provider_hangup(job.id, "busy", 0, "USER_BUSY")
    assert job_for(lead).state == "not_reachable"


@pytest.mark.asyncio
async def test_blocked_leads_are_never_dialed(queue):
    lead = make_lead(name="Blocked Bala", phone="+919812300130", opt_out=True)
    queue.enqueue([lead])
    await queue.tick()
    assert queue.dialer.dialed == []
    assert job_for(lead).state == "blocked" and job_for(lead).block_reason == "opted_out"


@pytest.mark.asyncio
async def test_consent_confirmed_unblocks_imported_leads(queue):
    lead = make_lead(name="Import Indu", phone="+919812300140", source="csv", consent=False)
    queue.enqueue([lead], consent_confirmed=True)
    await queue.tick()
    assert len(queue.dialer.dialed) == 1
    session = SessionLocal()
    assert session.get(Lead, lead).consent_source.startswith("campaign_confirmed")
    session.close()


@pytest.mark.asyncio
async def test_pause_and_stop(queue):
    leads = [make_lead(name=f"P{i}", phone=f"+91981230015{i}") for i in range(2)]
    queue.enqueue(leads)
    queue.pause()
    await queue.tick()
    assert queue.dialer.dialed == []
    assert queue.cancel_waiting() == 2
    queue.resume()
    await queue.tick()
    assert queue.dialer.dialed == []
    assert job_for(leads[0]).state == "cancelled"


@pytest.mark.asyncio
async def test_hangup_after_answer_is_left_to_the_engine(queue):
    lead = make_lead(name="Talk Tara", phone="+919812300160")
    queue.enqueue([lead])
    await queue.tick()
    job = job_for(lead)
    queue.on_answered(job.id)
    queue.on_provider_hangup(job.id, "completed", 75, "NORMAL_CLEARING")
    assert job_for(lead).state == "in_progress"  # engine marks it completed when the call is saved
