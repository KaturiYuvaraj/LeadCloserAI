"""
Credit protection (voice_agent/credits.py): when Sarvam credits finish or the key is rejected,
calling stops, the call in progress ends, and its lead goes back in the queue.
Offline: Sarvam is never contacted (the probe is stubbed).
"""

import asyncio
from types import SimpleNamespace

import pytest

from core.db import SessionLocal
from models import CallJob
from tests.test_dialer import job_for, make_lead, queue  # noqa: F401  (fixture)
from voice_agent import credits
from voice_agent import dialer as dialer_module
from voice_agent.dialer import SERVICE_FAILED
try:
    from voice_agent.session import BaseCallSession
except (ImportError, SyntaxError):
    BaseCallSession = None

# the real error Sarvam returned on 5 Nov 2026
NO_CREDITS = '{"error":{"message":"No credits available.","code":"insufficient_quota_error"}}'
BAD_KEY = '{"error":{"message":"Invalid or missing authentication credentials","code":"invalid_api_key_error"}}'


@pytest.fixture(autouse=True)
def clean_block():
    credits.clear("test")
    credits._last_probe = 0.0
    yield
    credits.clear("test")


def test_classify_sarvam_errors():
    assert credits.classify(NO_CREDITS) == "no_credits"
    assert credits.classify("SarvamTTSService error: TTS Error: 402: insufficient_quota_error") == "no_credits"
    assert credits.classify(BAD_KEY) == "invalid_key"
    assert credits.classify("Speaker 'x' is not recognized") is None  # a bad voice name is not a credit problem
    assert credits.classify("") is None


def test_only_credit_errors_block_calling():
    assert credits.report_error("connection reset by peer") is None and credits.blocked() is None
    assert credits.report_error(NO_CREDITS, "tts") == "no_credits"
    assert credits.blocked()["reason"] == "no_credits" and "dashboard.sarvam.ai" in credits.blocked()["message"]


@pytest.mark.asyncio
async def test_blocked_dialer_places_no_calls(queue):
    lead = make_lead(name="Credit Chandu", phone="+919812300301")
    queue.enqueue([lead])
    credits.report_error(NO_CREDITS, "test")
    credits._last_probe = 10 ** 12  # a probe is not due
    await queue.tick()
    assert queue.dialer.dialed == [] and job_for(lead).state == "queued"
    assert queue.status()["service_block"]["reason"] == "no_credits"


@pytest.mark.asyncio
async def test_dialer_resumes_when_the_probe_succeeds(queue, monkeypatch):
    lead = make_lead(name="Credit Chitra", phone="+919812300302")
    queue.enqueue([lead])
    credits.report_error(NO_CREDITS, "test")

    async def sarvam_works(now=None):
        credits.clear("probe ok")
        return True
    monkeypatch.setattr(credits, "probe", sarvam_works)
    await queue.tick()
    assert len(queue.dialer.dialed) == 1 and credits.blocked() is None


@pytest.mark.asyncio
async def test_resume_button_unblocks(queue):
    credits.report_error(NO_CREDITS, "test")
    queue.resume()
    assert credits.blocked() is None


@pytest.mark.asyncio
async def test_call_cut_off_by_credits_goes_back_in_the_queue_without_using_an_attempt(queue):
    lead = make_lead(name="Cut Kiran", phone="+919812300303")
    queue.enqueue([lead], max_attempts=2)
    await queue.tick()
    job = job_for(lead)
    assert job.state == "dialing" and job.attempt == 1
    queue.on_answered(job.id)
    credits.report_error(NO_CREDITS, "test")
    queue.on_call_saved(job.id, None, SERVICE_FAILED)
    job = job_for(lead)
    assert job.state == "queued" and job.attempt == 0 and job.last_disposition == SERVICE_FAILED


@pytest.mark.asyncio
async def test_requeued_lead_is_not_held_back_by_called_recently(queue, monkeypatch):
    lead = make_lead(name="Back Bhaskar", phone="+919812300304")
    queue.enqueue([lead])
    await queue.tick()
    job = job_for(lead)
    queue.on_answered(job.id)
    queue.on_call_saved(job.id, None, SERVICE_FAILED)
    await queue.tick()
    assert job_for(lead).state == "dialing"


def _session():
    sent = []
    fake = SimpleNamespace(service_failed=None, end_reason=None, ended_by=None, task=None, session_id="t",
                           send_event=lambda kind, **kw: sent.append((kind, kw)))
    return fake, sent


@pytest.mark.asyncio
async def test_session_ends_the_call_on_a_credit_error():
    if BaseCallSession is None:
        pytest.skip("BaseCallSession requires Pipecat 1.14+ (Python 3.10+)")
    fake, sent = _session()
    cancelled = []

    class Task:
        async def cancel(self):
            cancelled.append(True)
    fake.task = Task()
    assert await BaseCallSession.on_service_error(fake, NO_CREDITS, "tts") is True
    await asyncio.sleep(0)
    assert fake.service_failed == "no_credits" and fake.end_reason == "service_unavailable"
    assert cancelled and sent[0] == ("call_ending", {"reason": "service_unavailable"})


@pytest.mark.asyncio
async def test_session_ignores_unrelated_errors():
    if BaseCallSession is None:
        pytest.skip("BaseCallSession requires Pipecat 1.14+ (Python 3.10+)")
    fake, _ = _session()
    assert await BaseCallSession.on_service_error(fake, "websocket closed", "tts") is False
    assert fake.service_failed is None and credits.blocked() is None


@pytest.mark.asyncio
async def test_probe_keeps_blocking_while_sarvam_still_says_402(monkeypatch):
    credits.report_error(NO_CREDITS, "test")

    class Resp:
        status_code = 402

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return Resp()
    monkeypatch.setattr(credits.httpx, "AsyncClient", Client)
    assert await credits.probe() is False and credits.blocked() is not None
    Resp.status_code = 200
    assert await credits.probe() is True and credits.blocked() is None
