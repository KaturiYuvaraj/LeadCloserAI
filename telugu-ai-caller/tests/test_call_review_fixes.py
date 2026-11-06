"""
Fixes from the inbound test call of 6 Nov 2026 (call #8):
- the dashboard played an old browser recording (call_8.webm) instead of the call's WAV
- a booked demo was saved as "follow-up" because the booking check compared MEETING with meeting
- the AI offered "Monday 5th November" on Friday 6 November, and promised WhatsApp it can't send
- a demo today at 4 PM was booked next to a callback tomorrow at 4 PM
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

import main
import routers.calls as calls_router
from core.db import SessionLocal
from database import save_call_record
from models import CallJob
from tests.test_dialer import make_lead
from voice_agent import session as session_module
from voice_agent.actions import run_action
from voice_agent.session import BaseCallSession, calendar_hint, live_rules, whatsapp_note

IST = timezone(timedelta(hours=5, minutes=30))
FRIDAY_3PM = datetime(2026, 11, 6, 15, 12, tzinfo=IST)


# ---------------------------------------------------------------- booking check
def test_booked_meeting_is_recognised_in_the_stored_action_shape():
    action = asyncio.run(run_action("MEETING", "2026-11-06 16:00", {"id": make_lead(name="Meet Meena", phone="+919812300701")}))
    assert action["action"] == "meeting"  # stored lower-case
    fake = SimpleNamespace(actions=[action], session_id="t", BOOKED_STAGES=BaseCallSession.BOOKED_STAGES)
    out = BaseCallSession._check_booking(fake, {"deal_stage": "demo_scheduled", "outcome_label": "meeting_booked"})
    assert out["deal_stage"] == "demo_scheduled" and out["outcome_label"] == "meeting_booked"


# ---------------------------------------------------------------- calendar and prompt honesty
def test_calendar_gives_real_dates():
    text = calendar_hint(FRIDAY_3PM)
    assert "Today is Friday 6 November 2026" in text and "03:12 PM" in text
    assert "Tomorrow is Saturday 7 November" in text and "Monday 9 November" in text
    assert "5 November" not in text  # the date the AI invented


def test_prompt_carries_the_calendar_and_the_new_rules():
    rules = live_rules({"name": "Ravi"}, "out", FRIDAY_3PM.astimezone(timezone.utc))
    assert "Monday 9 November" in rules and "never guess a date or weekday" in rules
    assert "already passed today" in rules
    assert "Repeat back only what the customer actually said" in rules
    assert "script of the language you are speaking" in rules
    assert "our team will call you" in rules and "do not also add [CALLBACK]".lower() in rules.lower()
    assert "మీ బిజినెస్ కోసం డెమో" in rules  # the right/wrong script example
    assert "If the customer asks for a time today that is still ahead" in rules  # 4 PM at 3:12 PM is fine
    assert "have NOT chosen" in rules and "Never book a time the customer said they cannot do" in rules


def test_ai_does_not_claim_to_send_whatsapp_while_it_is_not_connected(monkeypatch):
    monkeypatch.setattr("voice_agent.actions._provider", lambda kind, name: None)
    assert "never say you are sending anything now" in whatsapp_note()
    monkeypatch.setattr("voice_agent.actions._provider", lambda kind, name: object())
    assert "say you are sending it now" in whatsapp_note()


# ---------------------------------------------------------------- meeting replaces callback
def test_meeting_cancels_a_waiting_callback():
    lead_id = make_lead(name="Conflict Chaya", phone="+919812300702")
    session = SessionLocal()
    session.add(CallJob(account_id=1, lead_id=lead_id, phone_e164="+919812300702", provider="pending", state="scheduled",
                        attempt=0, max_attempts=2, next_attempt_at=datetime.now() + timedelta(days=1),
                        last_disposition="callback_requested"))
    session.commit()
    session.close()
    result = asyncio.run(run_action("MEETING", "2026-11-06 16:00", {"id": lead_id}))
    assert result["result"]["callbacks_cancelled"] == 1
    session = SessionLocal()
    job = session.query(CallJob).filter(CallJob.lead_id == lead_id).one()
    assert job.state == "cancelled" and job.block_reason == "replaced_by_meeting"
    session.close()


# ---------------------------------------------------------------- recordings
@pytest.fixture
def recordings(tmp_path, monkeypatch):
    monkeypatch.setattr(calls_router, "RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(session_module, "RECORDINGS_DIR", tmp_path)
    return tmp_path


def _call_id():
    return save_call_record({"lead_id": make_lead(name="Rec Ramu", phone="+919812300703"), "call_type": "phone",
                             "duration_seconds": 50, "status": "completed", "deal_stage": "follow_up", "summary": "x"})


def _touch(path, age_seconds):
    path.write_bytes(b"audio")
    stamp = datetime.now().timestamp() - age_seconds
    os.utime(path, (stamp, stamp))


def test_dashboard_plays_the_newest_recording_not_a_leftover(recordings):
    call_id = _call_id()
    _touch(recordings / f"call_{call_id}.webm", 5 * 86400)   # an old browser call that had this id
    _touch(recordings / f"call_{call_id}.wav", 60)           # today's phone call
    response = TestClient(main.app).get(f"/api/calls/{call_id}/recording")
    assert response.status_code == 200 and response.headers["content-type"].startswith("audio/wav")


def test_a_browser_recording_is_still_served_when_it_is_the_newest(recordings):
    call_id = _call_id()
    _touch(recordings / f"call_{call_id}.wav", 5 * 86400)
    _touch(recordings / f"call_{call_id}.webm", 60)
    response = TestClient(main.app).get(f"/api/calls/{call_id}/recording")
    assert response.headers["content-type"].startswith("audio/webm")


def test_saving_a_phone_recording_removes_a_stale_webm(recordings, monkeypatch):
    monkeypatch.setattr(session_module, "update_call_recording", lambda call_id, url: None)
    (recordings / "call_77.webm").write_bytes(b"old")
    fake = SimpleNamespace(_audio=(b"\x00\x01" * 800, 16000, 2))
    assert BaseCallSession._save_recording(fake, 77) == "/api/calls/77/recording"
    assert (recordings / "call_77.wav").exists() and not (recordings / "call_77.webm").exists()
