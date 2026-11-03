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


# ---------------------------------------------------------------------------- Vobiz

import base64  # noqa: E402
import json  # noqa: E402

from pipecat.frames.frames import InputAudioRawFrame, InterruptionFrame, OutputAudioRawFrame  # noqa: E402
from pipecat.processors.frame_processor import FrameProcessorSetup  # noqa: E402

from voice_agent.vobiz import (  # noqa: E402
    VOBIZ_SAMPLE_RATE,
    VobizFrameSerializer,
    build_answer_xml,
    parse_start_message,
)


def test_answer_xml_streams_to_engine_then_hangs_up():
    xml = build_answer_xml("wss://example.com/api/voice/vobiz/stream?lead_id=1&lang=te-IN")
    assert '<Stream bidirectional="true"' in xml
    assert 'contentType="audio/x-l16;rate=16000"' in xml
    assert "wss://example.com/api/voice/vobiz/stream?lead_id=1&amp;lang=te-IN</Stream>" in xml
    assert xml.index("</Stream>") < xml.index("<Hangup/>")


def test_parse_start_message_reads_nested_and_top_level_fields():
    data = parse_start_message({
        "event": "start", "streamId": "s-top",
        "start": {"callId": "c1", "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}},
    })
    assert data["stream_id"] == "s-top"
    assert data["call_id"] == "c1"
    assert data["encoding"] == "mulaw"
    assert data["sample_rate"] == 8000

    data = parse_start_message({"event": "start", "start": {"streamId": "s-nested"}})
    assert data["stream_id"] == "s-nested"
    assert data["encoding"] == "l16"
    assert data["sample_rate"] == VOBIZ_SAMPLE_RATE


async def _setup_serializer(serializer, rate=16000):
    class _Setup:
        audio_in_sample_rate = rate
    await serializer.setup(_Setup())


@pytest.mark.asyncio
async def test_vobiz_serializer_audio_round_trip():
    serializer = VobizFrameSerializer(stream_id="s1")
    await _setup_serializer(serializer)

    pcm = (b"\x10\x00\xf0\xff" * 800)  # 100 ms of 16 kHz 16-bit audio
    inbound = await serializer.deserialize(json.dumps({
        "event": "media", "streamId": "s1", "media": {"payload": base64.b64encode(pcm).decode()},
    }))
    assert isinstance(inbound, InputAudioRawFrame)
    assert inbound.sample_rate == 16000 and inbound.audio == pcm

    outbound = json.loads(await serializer.serialize(OutputAudioRawFrame(audio=pcm, sample_rate=16000, num_channels=1)))
    assert outbound["event"] == "playAudio"
    assert outbound["streamId"] == "s1"
    assert outbound["media"]["contentType"] == "audio/x-l16"
    assert outbound["media"]["sampleRate"] == 16000
    assert base64.b64decode(outbound["media"]["payload"]) == pcm


@pytest.mark.asyncio
async def test_vobiz_serializer_barge_in_and_ignored_events():
    serializer = VobizFrameSerializer(stream_id="s2")
    await _setup_serializer(serializer)
    assert json.loads(await serializer.serialize(InterruptionFrame())) == {"event": "clearAudio", "streamId": "s2"}
    assert await serializer.deserialize(json.dumps({"event": "playedStream", "name": "tts"})) is None
    assert await serializer.deserialize("not json") is None


def test_vobiz_answer_endpoint_returns_stream_xml():
    from starlette.testclient import TestClient
    import main

    with TestClient(main.app) as client:
        resp = client.post("/api/voice/vobiz/answer?lead_id=7",
                           data={"From": "+919876543210", "To": "+918040000000", "CallUUID": "call-1"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/xml")
        assert "/api/voice/vobiz/stream?lead_id=7" in resp.text
        assert "call_id=call-1" in resp.text
        assert "<Hangup/>" in resp.text


def test_vobiz_stream_rejects_missing_stream_id():
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import main

    with TestClient(main.app) as client:
        with client.websocket_connect("/api/voice/vobiz/stream") as ws:
            ws.send_json({"event": "start", "start": {}})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_text()
            assert closed.value.code == 1008


# ---------------------------------------------------------------------------- AI ends the call

from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame  # noqa: E402

from voice_agent.conclusion import CALL_COMPLETED_MARKER, CallConclusionFilter, split_marker  # noqa: E402


@pytest.mark.parametrize("text,emit,hold,found", [
    ("Goodbye! [CALL_COMPLETED]", "Goodbye! ", "", True),
    ("Goodbye! [CALL", "Goodbye! ", "[CALL", False),
    ("Price is [about] 25k", "Price is [about] 25k", "", False),
    ("Thanks [", "Thanks ", "[", False),
    ("no marker here", "no marker here", "", False),
])
def test_split_marker(text, emit, hold, found):
    assert split_marker(text) == (emit, hold, found)


async def _run_filter(chunks, monkeypatch):
    """Feed streamed tokens through the filter; return (text sent on to TTS, concluded?)."""
    from pipecat.processors.frame_processor import FrameProcessor

    async def skip_base_processing(self, frame, direction):
        return None

    monkeypatch.setattr(FrameProcessor, "process_frame", skip_base_processing)

    spoken, concluded = [], []

    async def on_concluded():
        concluded.append(True)

    flt = CallConclusionFilter(on_concluded)

    async def capture(frame, direction=None):
        if isinstance(frame, LLMTextFrame):
            spoken.append(frame.text)

    monkeypatch.setattr(flt, "push_frame", capture)
    for frame in [LLMFullResponseStartFrame(), *[LLMTextFrame(c) for c in chunks], LLMFullResponseEndFrame()]:
        await flt.process_frame(frame, None)
    return "".join(spoken), bool(concluded)


@pytest.mark.asyncio
async def test_filter_removes_marker_split_across_tokens(monkeypatch):
    text, concluded = await _run_filter(["ఉంటానండి, సెలవు! ", "[CALL", "_COMPL", "ETED]"], monkeypatch)
    assert CALL_COMPLETED_MARKER not in text
    assert "[" not in text
    assert text.strip() == "ఉంటానండి, సెలవు!"
    assert concluded


@pytest.mark.asyncio
async def test_filter_passes_normal_reply_and_brackets(monkeypatch):
    text, concluded = await _run_filter(["Our price is ", "[starting] ₹25,000", ". Shall we book a demo?"], monkeypatch)
    assert text == "Our price is [starting] ₹25,000. Shall we book a demo?"
    assert not concluded
