"""
Vobiz webhook secret (voice_agent/webhook_auth.py): with VOBIZ_WEBHOOK_SECRET set, the Answer URL,
Hangup URL and audio stream reject requests without the key. Offline.
"""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from voice_agent import webhook_auth
from voice_agent.outbound import DialRequest, VobizDialer

SECRET = "s3cret-for-tests-only"


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("VOBIZ_WEBHOOK_SECRET", SECRET)


def test_no_secret_means_open_for_local_development(client, monkeypatch):
    monkeypatch.delenv("VOBIZ_WEBHOOK_SECRET", raising=False)
    assert not webhook_auth.enabled() and webhook_auth.is_valid(None)
    assert client.post("/api/voice/vobiz/answer", data={"CallUUID": "x"}).status_code == 200


def test_answer_url_rejects_strangers(client, secret):
    assert client.post("/api/voice/vobiz/answer", data={"CallUUID": "x"}).status_code == 403
    assert client.post("/api/voice/vobiz/answer?key=wrong", data={"CallUUID": "x"}).status_code == 403
    assert client.get("/api/voice/vobiz/answer").status_code == 403


def test_answer_url_accepts_vobiz_and_passes_the_key_on_to_the_stream(client, secret):
    response = client.post(f"/api/voice/vobiz/answer?key={SECRET}&lead_id=1", data={"CallUUID": "x"})
    assert response.status_code == 200 and "<Stream" in response.text
    assert f"key={SECRET}" in response.text  # the audio stream must carry it too


def test_hangup_url_rejects_fake_call_results(client, secret):
    assert client.post("/api/voice/vobiz/hangup?job_id=1", data={"CallStatus": "completed"}).status_code == 403
    assert client.post(f"/api/voice/vobiz/hangup?key={SECRET}", data={"CallStatus": "completed"}).status_code == 200


def test_audio_stream_rejects_strangers(client, secret):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/voice/vobiz/stream") as ws:
            ws.receive_text()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/voice/vobiz/stream?key=wrong") as ws:
            ws.receive_text()


def test_calls_we_place_carry_the_key(secret, monkeypatch):
    monkeypatch.setenv("VOBIZ_AUTH_ID", "id")
    monkeypatch.setenv("VOBIZ_AUTH_TOKEN", "token")
    monkeypatch.setenv("VOBIZ_CALLER_ID", "+917965482229")
    sent = {}

    class Resp:
        status_code = 200
        content = b"{}"
        def json(self): return {"request_uuid": "u1"}

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            sent.update(json); return Resp()
    monkeypatch.setattr("voice_agent.outbound.httpx.AsyncClient", Client)
    import asyncio
    asyncio.run(VobizDialer().dial(DialRequest(job_id=5, lead_id=9, to_number="+919812300601",
                                               language="te-IN", max_call_seconds=600)))
    assert f"key={SECRET}" in sent["answer_url"] and f"key={SECRET}" in sent["hangup_url"]
