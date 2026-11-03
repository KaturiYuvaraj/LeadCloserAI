"""
Tests for the real-time voice engine (voice_agent + routers/voice).
Offline: no Sarvam calls, no WebRTC connection.
"""

import pytest

pytest.importorskip("pipecat", reason="Pipecat not installed (requires Python 3.10-3.13)")

from pipecat.frames.frames import TTSUpdateSettingsFrame  # noqa: E402

from voice_agent.language import VOICES, LanguageRouter, detect_language  # noqa: E402
from voice_agent.session import wait_ms_to_vad_stop_secs  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("సరేనండి, మాకు వెబ్‌సైట్ కావాలి", "te-IN"),
    ("हमें एक मोबाइल ऐप चाहिए", "hi-IN"),
    ("Can you show me a demo tomorrow?", "en-IN"),
    ("haan ji bilkul theek hai", "hi-IN"),
    ("sare andi meeku entha kavali", "te-IN"),
    ("ok", None),
])
def test_detect_language(text, expected):
    assert detect_language(text) == expected


def test_router_switches_voice_only_when_language_changes():
    router = LanguageRouter("te-IN")

    annotated, switch = router.prepare("మాకు యాప్ కావాలి")
    assert switch is None
    assert annotated.endswith("(Reply only in Telugu.)")

    annotated, switch = router.prepare("हमें ऐप चाहिए")
    assert isinstance(switch, TTSUpdateSettingsFrame)
    assert switch.delta.voice == VOICES["hi-IN"]
    assert switch.delta.language == "hi-IN"
    assert router.current_language == "hi-IN"
    assert annotated.endswith("(Reply only in Hindi.)")

    annotated, switch = router.prepare("ठीक है")
    assert switch is None


def test_router_keeps_language_for_undecidable_text():
    router = LanguageRouter("en-IN")
    annotated, switch = router.prepare("ok")
    assert switch is None
    assert router.current_language == "en-IN"
    assert annotated.endswith("(Reply only in English.)")


def test_router_defaults_unknown_initial_language_to_telugu():
    assert LanguageRouter("ta-IN").current_language == "te-IN"


@pytest.mark.parametrize("wait_ms,expected", [
    (700, 0.3), (900, 0.5), (1300, 0.9), (None, 0.5), ("bad", 0.5), (100, 0.3), (5000, 1.2),
])
def test_reply_wait_maps_to_vad_stop_secs(wait_ms, expected):
    assert wait_ms_to_vad_stop_secs(wait_ms) == expected


@pytest.mark.asyncio
async def test_voice_config_endpoint_reports_engine(async_client):
    resp = await async_client.get("/api/voice/config.js")
    assert resp.status_code == 200
    assert "window.LC_VOICE_ENGINE" in resp.text


@pytest.mark.asyncio
async def test_unknown_voice_session_returns_404(async_client):
    resp = await async_client.get("/api/voice/sessions/does-not-exist/summary?wait_seconds=1")
    assert resp.status_code == 404
    resp = await async_client.post("/api/voice/sessions/does-not-exist/hangup")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------- phone path

from voice_agent.session import PhoneCallSession, as_text, find_lead_by_phone, parse_custom_parameters  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    (["E-Commerce Website", "Mobile App"], "E-Commerce Website, Mobile App"),
    (None, ""),
    ("text", "text"),
    (42, "42"),
    ({"a": 1}, '{"a": 1}'),
    (["x", None, ""], "x"),
])
def test_as_text_never_returns_lists(value, expected):
    assert as_text(value) == expected


@pytest.mark.parametrize("raw,expected", [
    ({"lead_id": 5}, {"lead_id": "5"}),
    ("lead_id=7&lang=hi-IN", {"lead_id": "7", "lang": "hi-IN"}),
    ('{"lead_id": "9"}', {"lead_id": "9"}),
    ("", {}),
    (None, {}),
])
def test_parse_custom_parameters(raw, expected):
    assert parse_custom_parameters(raw) == expected


def _make_lead(phone: str) -> dict:
    from database import create_lead, get_lead_by_id
    lead_id = create_lead({"name": "Phone Test Lead", "phone": phone, "service_needed": "Website"})
    return get_lead_by_id(lead_id)


def test_find_lead_by_phone_ignores_prefixes():
    lead = _make_lead("+91 98480 22338")
    for caller in ("+919848022338", "09848022338", "9848022338", "+91-98480-22338"):
        found = find_lead_by_phone(caller)
        assert found and found["id"] == lead["id"], caller
    assert find_lead_by_phone("12345") is None


def test_phone_session_outbound_uses_lead_id_parameter():
    lead = _make_lead("+91 90000 11122")
    session = PhoneCallSession(
        websocket=None,
        call_data={"stream_id": "s1", "call_id": "c1", "from": "+918040000000", "to": "+919000011122",
                   "custom_parameters": {"lead_id": str(lead["id"])}},
    )
    assert session.direction == "out"
    assert session.lead_id == lead["id"]
    assert session.call_sid == "c1"
    assert session.extra_result_fields() == {"call_sid": "c1"}


def test_phone_session_inbound_matches_caller_number():
    lead = _make_lead("+91 90000 33344")
    session = PhoneCallSession(
        websocket=None,
        call_data={"stream_id": "s2", "call_id": "c2", "from": "09000033344", "to": "+918040000000"},
    )
    assert session.direction == "in"
    assert session.lead_id == lead["id"]
    assert session.phone_number() == "09000033344"


def test_phone_session_unknown_caller_has_no_lead():
    session = PhoneCallSession(
        websocket=None,
        call_data={"stream_id": "s3", "call_id": "c3", "from": "+919111111111", "to": "+918040000000"},
        query_params={"lang": "hi-IN"},
    )
    assert session.direction == "in"
    assert session.lead_id is None
    assert session.language == "hi-IN"


def test_exotel_stream_rejects_non_exotel_handshake():
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import main

    with TestClient(main.app) as client:
        with client.websocket_connect("/api/voice/exotel/stream") as ws:
            ws.send_json({"event": "connected"})
            ws.send_json({"event": "start", "start": {"streamSid": "x"}})  # not Exotel's format
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_text()
            assert closed.value.code == 1008
