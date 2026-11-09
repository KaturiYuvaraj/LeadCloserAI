"""
The engine switch: our engine (Shreya) or Sarvam's own agent (Shriya) places the calls.
Offline: Sarvam's API is replaced by a stub that records the request; nothing is dialled or billed.
"""

import asyncio
import json
from datetime import timedelta

import pytest
from starlette.testclient import TestClient

import main
from core.db import SessionLocal
from models import Call, CallJob
from tests.test_call_now_button import api  # noqa: F401  (fixture)
from tests.test_dialer import MONDAY_11_IST, job_for, make_lead, queue  # noqa: F401  (fixture)
from voice_agent import dialer as dialer_module
from voice_agent import samvaad
from voice_agent.outbound import DialRequest
from voice_agent.rules import db_time

SETTINGS = {"SAMVAAD_API_KEY": "test-key", "SAMVAAD_ORG_ID": "org1", "SAMVAAD_WORKSPACE_ID": "ws1",
            "SAMVAAD_APP_ID": "Conversatio-test", "SAMVAAD_APP_VERSION": "2", "SAMVAAD_CONNECTION_ID": "conn1",
            "SAMVAAD_AGENT_NUMBER": "+917965482229"}


class StubSamvaad(samvaad.SamvaadDialer):
    def __init__(self):
        self.dialed = []

    async def dial(self, req):
        self.dialed.append(req)
        return f"attempt-{req.job_id}"


@pytest.fixture
def configured(monkeypatch):
    for name, value in SETTINGS.items():
        monkeypatch.setenv(name, value)
    yield
    samvaad.set_engine("pipecat")


@pytest.fixture
def shriya(queue, configured):
    queue.samvaad = StubSamvaad()
    samvaad.set_engine("samvaad")
    return queue


def run(queue):
    asyncio.run(queue.tick())


def test_default_is_our_engine_and_samvaad_needs_its_settings(api):
    data = api.get("/api/dialer/engine").json()
    assert data["engine"] == "pipecat"
    sarvam = next(o for o in data["options"] if o["id"] == "samvaad")
    assert not sarvam["ready"] and "Agent ID" in sarvam["missing"]
    resp = api.post("/api/dialer/engine", json={"engine": "samvaad"})
    assert resp.status_code == 400 and "not set up" in resp.json()["detail"]
    assert api.post("/api/dialer/engine", json={"engine": "other"}).status_code == 400


def test_switching_needs_login():
    client = TestClient(main.app)
    assert client.get("/api/dialer/engine").status_code == 401
    assert client.post("/api/dialer/engine", json={"engine": "pipecat"}).status_code == 401


def test_switch_and_back(api, configured):
    assert api.post("/api/dialer/engine", json={"engine": "samvaad"}).json()["engine"] == "samvaad"
    lead = make_lead(name="Engine Eshwar", phone="+919812300951")
    check = api.get(f"/api/dialer/call-now/{lead}/check").json()
    assert check["engine"] == "samvaad" and check["engine_label"] == "Sarvam Agent (Shriya)" and not check["simulated"]
    assert api.post("/api/dialer/engine", json={"engine": "pipecat"}).json()["engine"] == "pipecat"


def test_request_matches_sarvams_api(configured):
    body = samvaad.build_request(DialRequest(job_id=7, lead_id=3, to_number="+919812300952",
                                             language="hi-IN", lead_name="Ravi"))
    app = body["app_config"]
    assert app["app_id"] == "Conversatio-test" and app["app_version"] == 2
    assert app["connection_config"] == {"connection_id": "conn1", "agent_phone_number": "+917965482229"}
    assert app["agent_variables"] == {"user_name": "Ravi"} and app["app_overrides"] == {"initial_language_name": "Hindi"}
    assert body["user_config"] == {"user_phone_number": "+919812300952"}
    assert "/api/voice/samvaad/webhook?" in body["webhook_config"]["url"] and "job_id=7" in body["webhook_config"]["url"]
    unnamed = samvaad.build_request(DialRequest(job_id=8, lead_id=3, to_number="+919812300952",
                                                lead_name="Manual call 9812300952"))
    assert "agent_variables" not in unnamed["app_config"] and "app_overrides" not in unnamed["app_config"]


def test_calling_rules_still_apply(shriya):
    blocked = make_lead(name="Opted Out Omkar", phone="+919812300953", opt_out=True)
    shriya.enqueue([blocked], consent_confirmed=True, priority=0)
    run(shriya)
    assert shriya.samvaad.dialed == [] and job_for(blocked).state == "blocked"


def test_jobs_go_to_sarvam_and_a_late_report_is_never_redialled(shriya, monkeypatch):
    lead = make_lead(name="Shriya Sita", phone="+919812300954")
    shriya.enqueue([lead], consent_confirmed=True, priority=0)
    run(shriya)
    assert len(shriya.samvaad.dialed) == 1 and shriya.dialer.dialed == []
    job = job_for(lead)
    assert job.provider == "samvaad" and job.state == "dialing" and job.provider_call_id == f"attempt-{job.id}"

    # 5 minutes later (a normal ringing timeout has passed) the call is still Sarvam's
    monkeypatch.setattr(dialer_module, "utcnow", lambda: MONDAY_11_IST + timedelta(minutes=5))
    run(shriya)
    assert job_for(lead).state == "dialing" and len(shriya.samvaad.dialed) == 1

    # no report at all: closed, not dialled again
    monkeypatch.setattr(dialer_module, "utcnow", lambda: MONDAY_11_IST + timedelta(minutes=45))
    run(shriya)
    late = job_for(lead)
    assert late.state == "completed" and late.last_disposition == "no_report" and len(shriya.samvaad.dialed) == 1


def test_connected_result_is_saved_without_follow_ups(api, shriya, monkeypatch):
    monkeypatch.setattr("routers.voice.call_queue", shriya)
    lead = make_lead(name="Result Rani", phone="+919812300955")
    shriya.enqueue([lead], consent_confirmed=True, priority=0)
    run(shriya)
    job = job_for(lead)
    payload = {
        "attempt_id": f"attempt-{job.id}", "status": "connected", "duration": 70, "interaction_id": "int-1",
        "channel_info": {"channel_type": "v2v", "channel_provider": "vobiz", "agent_phone_number": "+917965482229"},
        "final_agent_variables": {"call_status": "qualified", "project_type": "website", "call_summary": "Wants a website."},
        "webhook_config": {"url": "x", "metadata": {"job_id": job.id, "lead_id": lead}},
        "interaction_transcript": [{"role": "agent", "en_text": "Hello, this is Shriya."},
                                   {"role": "user", "en_text": "I need a website."}],
    }
    assert TestClient(main.app).post(f"/api/voice/samvaad/webhook?job_id={job.id}", json=payload).json()["success"]
    done = job_for(lead)
    assert done.state == "completed" and done.call_id
    session = SessionLocal()
    try:
        call = session.get(Call, done.call_id)
        assert call.talk_seconds == 70 and call.provider_call_sid == f"attempt-{job.id}"
        assert "Sarvam Agent (Shriya)" in call.summary and "int-1" in call.summary
        transcript = call.transcript if isinstance(call.transcript, list) else json.loads(call.transcript)
        assert transcript[0] == {"role": "assistant", "content": "Hello, this is Shriya."}
        assert "website" in call.extracted_requirements and call.outcome == "qualified" and call.summary.startswith("Wants a website.")
        assert session.query(CallJob).filter(CallJob.lead_id == lead).count() == 1  # no follow-up queued
    finally:
        session.close()
    # a repeated report changes nothing
    TestClient(main.app).post(f"/api/voice/samvaad/webhook?job_id={job.id}", json=payload)
    assert job_for(lead).call_id == done.call_id


def test_unanswered_is_not_retried(shriya):
    lead = make_lead(name="Busy Bhanu", phone="+919812300956")
    shriya.enqueue([lead], consent_confirmed=True, priority=0)
    run(shriya)
    job = job_for(lead)
    shriya.on_samvaad_result(job.id, {"attempt_id": "a", "status": "no_answer"})
    after = job_for(lead)
    assert after.state == "not_reachable" and after.last_disposition == "no_answer"
    session = SessionLocal()
    try:
        assert session.query(CallJob).filter(CallJob.lead_id == lead).count() == 1
    finally:
        session.close()


def test_webhook_needs_the_secret(monkeypatch):
    monkeypatch.setenv("VOBIZ_WEBHOOK_SECRET", "s3cret")
    client = TestClient(main.app)
    assert client.post("/api/voice/samvaad/webhook?job_id=1", json={"status": "connected"}).status_code == 403
    assert client.post("/api/voice/samvaad/webhook?job_id=999999&key=s3cret", json={"status": "connected"}).json()["success"]


def test_noise_filter_is_off_unless_asked_for(monkeypatch):
    from voice_agent.session import BaseCallSession
    session = BaseCallSession.__new__(BaseCallSession)
    session.call_type = "phone"
    monkeypatch.delenv("VOICE_NOISE_FILTER", raising=False)
    assert session.transport_audio_filter() is None


def test_a_refused_sarvam_dial_is_not_retried(shriya):
    class Refusing(StubSamvaad):
        async def dial(self, req):
            from voice_agent.outbound import DialError
            raise DialError('Sarvam Agent 401: {"details":"Invalid API key format."}')

    shriya.samvaad = Refusing()
    lead = make_lead(name="Key Kiran", phone="+919812300957")
    shriya.enqueue([lead], consent_confirmed=True, priority=0)
    run(shriya)
    job = job_for(lead)
    assert job.state == "not_reachable" and "Invalid API key" in job.last_error and job.next_attempt_at is not None
    session = SessionLocal()
    try:
        assert session.query(CallJob).filter(CallJob.lead_id == lead, CallJob.state.in_(("queued", "retry_scheduled", "scheduled"))).count() == 0
    finally:
        session.close()


def test_office_background_mixes_quietly_at_the_line_rate(monkeypatch):
    import numpy as np
    from voice_agent import background
    monkeypatch.delenv("VOICE_BACKGROUND_SOUND", raising=False)
    for rate in (8000, 16000):
        mixer = background.background_mixer()
        assert mixer is not None
        asyncio.run(mixer.start(rate))
        silence = bytes(rate // 50 * 2)  # 20 ms of silence
        out = np.frombuffer(asyncio.run(mixer.mix(silence)), dtype=np.int16)
        assert len(out) == rate // 50 and 0 < np.abs(out).max() < 6000  # audible but soft
    monkeypatch.setenv("VOICE_BACKGROUND_SOUND", "off")
    assert background.background_mixer() is None
