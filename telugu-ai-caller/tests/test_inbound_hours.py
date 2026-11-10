"""
AI answering hours for incoming calls (voice_agent/inbound_hours.py): inside the hours the AI answers,
outside them Vobiz forwards the call to the team's number. Offline: no real calls.
"""

from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

import main
from core.auth import create_access_token
from services.price_list import PRICE_LIST_FOR_AI
from voice_agent import inbound_hours
from voice_agent.rules import IST


def at(hour, minute=0):
    return datetime(2026, 11, 10, hour, minute, tzinfo=IST).astimezone(timezone.utc)


@pytest.fixture(autouse=True)
def fresh_settings():
    inbound_hours._file().unlink(missing_ok=True)
    yield
    inbound_hours._file().unlink(missing_ok=True)


@pytest.fixture
def night_shift():
    return inbound_hours.save_settings({"enabled": True, "start": "20:00", "end": "10:00",
                                        "transfer_number": "+91 77802 36242"})


def test_off_by_default_so_the_ai_answers_every_call():
    assert inbound_hours.get_settings()["enabled"] is False
    assert inbound_hours.transfer_number_now(at(14)) == ""


def test_hours_that_cross_midnight(night_shift):
    assert night_shift["transfer_number"] == "+917780236242"
    for hour in (20, 23, 0, 3, 9):
        assert inbound_hours.transfer_number_now(at(hour)) == "", hour
    assert inbound_hours.transfer_number_now(at(9, 59)) == ""
    for hour in (10, 12, 19):
        assert inbound_hours.transfer_number_now(at(hour)) == "+917780236242", hour
    assert inbound_hours.transfer_number_now(at(19, 59)) == "+917780236242"


def test_daytime_hours():
    s = inbound_hours.save_settings({"enabled": True, "start": "10:00", "end": "20:00", "transfer_number": "+917780236242"})
    assert inbound_hours.in_ai_hours(s, at(12)) and not inbound_hours.in_ai_hours(s, at(21))


@pytest.mark.parametrize("bad", [
    {"enabled": True, "start": "20:00", "end": "10:00", "transfer_number": ""},
    {"enabled": True, "start": "20:00", "end": "20:00", "transfer_number": "+917780236242"},
    {"enabled": True, "start": "8pm", "end": "10:00", "transfer_number": "+917780236242"},
    {"enabled": True, "start": "20:00", "end": "10:00", "transfer_number": "123"},
])
def test_bad_settings_are_refused(bad):
    with pytest.raises(ValueError):
        inbound_hours.save_settings(bad)


def test_incoming_call_outside_ai_hours_is_forwarded(night_shift, monkeypatch):
    monkeypatch.delenv("VOBIZ_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("VOBIZ_CALLER_ID", "+917965482229")
    monkeypatch.setattr(inbound_hours, "transfer_number_now", lambda now_utc=None: "+917780236242")
    body = TestClient(main.app).post("/api/voice/vobiz/answer",
                                     data={"CallUUID": "x", "From": "+919000000001", "To": "+917965482229"}).text
    assert '<Dial callerId="+917965482229"' in body and "<Number>+917780236242</Number>" in body
    assert "<Stream" not in body


def test_incoming_call_inside_ai_hours_and_our_own_calls_reach_the_ai(night_shift, monkeypatch):
    monkeypatch.delenv("VOBIZ_WEBHOOK_SECRET", raising=False)
    client = TestClient(main.app)
    monkeypatch.setattr(inbound_hours, "transfer_number_now", lambda now_utc=None: "")
    assert "<Stream" in client.post("/api/voice/vobiz/answer", data={"CallUUID": "x", "From": "+919000000001"}).text
    # our outgoing calls carry the lead: never forwarded, whatever the time
    monkeypatch.setattr(inbound_hours, "transfer_number_now", lambda now_utc=None: "+917780236242")
    assert "<Stream" in client.post("/api/voice/vobiz/answer?lead_id=1", data={"CallUUID": "x"}).text


def test_dashboard_api_saves_and_reports():
    assert TestClient(main.app).get("/api/inbound/hours").status_code == 401
    client = TestClient(main.app)
    client.headers["Authorization"] = "Bearer " + create_access_token(1, 1, "admin@leadcloser.ai", "owner")
    r = client.post("/api/inbound/hours", json={"enabled": True, "start": "20:00", "end": "10:00",
                                                "transfer_number": "7780236242"})
    assert r.status_code == 200, r.text
    assert r.json()["transfer_number"] == "+917780236242" and "ai_answering_now" in r.json()
    assert client.get("/api/inbound/hours").json()["start"] == "20:00"
    assert client.post("/api/inbound/hours", json={"enabled": True, "start": "20:00", "end": "10:00"}).status_code == 400


def test_growth_and_premium_apps_explain_the_higher_price():
    assert "Business Growth Application" in PRICE_LIST_FOR_AI
    assert "Enterprise & Scalable Platform" in PRICE_LIST_FOR_AI
    assert "lead generation" in PRICE_LIST_FOR_AI
    assert "never promise a specific feature" in PRICE_LIST_FOR_AI
