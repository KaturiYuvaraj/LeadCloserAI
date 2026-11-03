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
