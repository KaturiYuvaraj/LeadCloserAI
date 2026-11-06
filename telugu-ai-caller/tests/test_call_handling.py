"""
Tests for real-call handling: machines (voicemail / IVR / carrier messages), caller
behaviour (hold, opt-out, human, upset), silence, action markers and their CRM
effects, knowledge base, analytics and phone recordings.
Offline: no Sarvam calls, no phone line.
"""

import io
import wave
from datetime import datetime, timezone

import pytest

pytest.importorskip("pipecat.services.sarvam", reason="Pipecat Sarvam service not installed")

from pipecat.frames.frames import (  # noqa: E402
    LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame, TranscriptionFrame,
    TTSSpeakFrame, UserIdleTimeoutUpdateFrame,
)

from core.db import SessionLocal  # noqa: E402
from database import create_lead  # noqa: E402
from models import CallJob, Lead, OptOut  # noqa: E402
from voice_agent import actions  # noqa: E402
from voice_agent.call_guard import CallGuard, caller_signals, classify_automated, is_hold_request  # noqa: E402
from voice_agent.conclusion import CallConclusionFilter, split_actions  # noqa: E402
from voice_agent.knowledge import KnowledgeBase, extract_text  # noqa: E402
from voice_agent.rules import IST  # noqa: E402
from voice_agent.session import BaseCallSession, live_rules  # noqa: E402

NOW = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)  # Tue 3 Nov 2026, 11:30 IST


# ----------------------------------------------------------------------------- machines

@pytest.mark.parametrize("text,kind", [
    ("The number you are calling is currently switched off", "unreachable"),
    ("The subscriber you have dialled is not reachable, please try later", "unreachable"),
    ("आप जिस नंबर पर कॉल कर रहे हैं वह अभी स्विच ऑफ है", "unreachable"),
    ("మీరు కాల్ చేస్తున్న నంబర్ ప్రస్తుతం స్విచ్ ఆఫ్ చేయబడి ఉంది", "unreachable"),
    ("Please leave a message after the beep", "voicemail"),
    ("I'm not available to take your call right now", "voicemail"),
    ("For English press 1, for Hindi press 2", "ivr"),
    ("हिंदी के लिए 2 दबाएं", "ivr"),
    ("తెలుగు కోసం 1 నొక్కండి", "ivr"),
])
def test_machines_are_detected(text, kind):
    assert classify_automated(text) == kind


@pytest.mark.parametrize("text", [
    "Hello, who is this?", "హలో చెప్పండి", "हाँ जी बोलिए", "I'm busy right now, call later",
    "Yes I need a website for my shop", "Switch to English please",
])
def test_people_are_not_machines(text):
    assert classify_automated(text) is None


# ----------------------------------------------------------------------------- people

@pytest.mark.parametrize("text,signals", [
    ("one minute please", ["hold"]),
    ("ఒక్క నిమిషం అండి", ["hold"]),
    ("एक मिनट रुकिए", ["hold"]),
    ("hold on", ["hold"]),
    ("Please don't call me again", ["opt_out"]),
    ("मुझे दोबारा कॉल मत करना", ["opt_out"]),
    ("నాకు మళ్ళీ కాల్ చేయకండి", ["opt_out"]),
    ("Can I talk to a real person?", ["human"]),
    ("This is a scam, stop wasting my time", ["upset"]),
    ("Wait, what is the price of the website and how long does it take?", []),
])
def test_caller_signals(text, signals):
    assert caller_signals(text) == signals


def test_long_sentence_with_minute_is_not_a_hold():
    assert not is_hold_request("can you send it in one minute on whatsapp with all the prices please")


# ----------------------------------------------------------------------------- action markers

@pytest.mark.parametrize("text,emit,hold,found", [
    ("Sure! [CALLBACK: 2026-11-04 17:30] [CALL_COMPLETED]", "Sure!  ", "", [("CALLBACK", "2026-11-04 17:30"), ("CALL_COMPLETED", "")]),
    ("Bye [CALLBACK: 2026-1", "Bye ", "[CALLBACK: 2026-1", []),
    ("Price is [about] 25k", "Price is [about] 25k", "", []),
    ("Okay [DO_NOT_CALL][CALL_COMPLETED]", "Okay ", "", [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")]),
    ("[send_whatsapp: quotation for website]", "", "", [("SEND_WHATSAPP", "quotation for website")]),
])
def test_split_actions(text, emit, hold, found):
    assert split_actions(text) == (emit, hold, found)


@pytest.mark.asyncio
async def test_filter_reports_actions_split_across_tokens(monkeypatch):
    from pipecat.processors.frame_processor import FrameProcessor

    async def skip(self, frame, direction):
        return None

    monkeypatch.setattr(FrameProcessor, "process_frame", skip)
    spoken, got, concluded = [], [], []

    async def on_action(tag, arg):
        got.append((tag, arg))

    async def on_concluded():
        concluded.append(True)

    flt = CallConclusionFilter(on_concluded, on_action=on_action)

    async def capture(frame, direction=None):
        if isinstance(frame, LLMTextFrame):
            spoken.append(frame.text)

    monkeypatch.setattr(flt, "push_frame", capture)
    chunks = ["సరే అండి, రేపు సాయంత్రం కాల్ చేస్తాను. ", "[CALL", "BACK: 2026-11-04 ", "17:30]", " [CALL_COMP", "LETED]"]
    for frame in [LLMFullResponseStartFrame(), *[LLMTextFrame(c) for c in chunks], LLMFullResponseEndFrame()]:
        await flt.process_frame(frame, None)
    assert "[" not in "".join(spoken)
    assert got == [("CALLBACK", "2026-11-04 17:30")]
    assert concluded


# ----------------------------------------------------------------------------- actions → CRM

def _lead(phone, name="Action Anil"):
    return create_lead({"name": name, "phone": phone, "service_needed": "Website"})


@pytest.mark.parametrize("arg,expected_ist", [
    ("2026-11-04 17:30", "2026-11-04 17:30"),
    ("2026-11-05", "2026-11-05 11:00"),
    ("18:00", "2026-11-03 18:00"),
    ("09:00", "2026-11-04 09:00"),  # already past today → tomorrow
])
def test_parse_when(arg, expected_ist):
    assert actions.parse_when(arg, NOW).astimezone(IST).strftime("%Y-%m-%d %H:%M") == expected_ist


def test_parse_when_rejects_nonsense():
    assert actions.parse_when("whenever you like", NOW) is None


@pytest.mark.asyncio
async def test_callback_action_schedules_a_dialer_job():
    lead_id = _lead("+919812309001")
    record = await actions.run_action("CALLBACK", "2026-11-04 17:30", {"id": lead_id}, "te-IN", now_utc=NOW)
    assert record["result"]["ok"]
    session = SessionLocal()
    job = session.query(CallJob).filter(CallJob.lead_id == lead_id).order_by(CallJob.id.desc()).first()
    lead = session.get(Lead, lead_id)
    assert job.state == "scheduled" and job.last_disposition == "callback_requested"
    assert lead.variables["next_callback_at"] == "2026-11-04 17:30 IST"
    session.close()


@pytest.mark.asyncio
async def test_do_not_call_action_opts_out_and_cancels_jobs():
    lead_id = _lead("+919812309002")
    await actions.run_action("CALLBACK", "2026-11-04 17:30", {"id": lead_id}, now_utc=NOW)
    record = await actions.run_action("DO_NOT_CALL", "", {"id": lead_id})
    assert record["result"] == {"ok": True, "cancelled_jobs": 1}
    session = SessionLocal()
    lead = session.get(Lead, lead_id)
    assert lead.opt_out is True
    assert session.query(OptOut).filter(OptOut.phone_e164 == lead.phone_e164).count() == 1
    session.close()


@pytest.mark.asyncio
async def test_whatsapp_and_handoff_actions_without_providers_are_queued(monkeypatch):
    monkeypatch.setattr(actions, "_provider", lambda kind, name: None)
    lead_id = _lead("+919812309003")
    await actions.run_action("SEND_WHATSAPP", "website quotation", {"id": lead_id, "phone": "+919812309003"})
    await actions.run_action("HUMAN_HANDOFF", "", {"id": lead_id})
    await actions.run_action("MEETING", "2026-11-05 11:00", {"id": lead_id}, now_utc=NOW)
    session = SessionLocal()
    variables = session.get(Lead, lead_id).variables
    assert variables["pending_whatsapp"][0]["what"] == "website quotation"
    assert "needs_human" in variables
    assert variables["meeting_at"] == "2026-11-05 11:00 IST" and variables["status"] == "DEMO_BOOKED"
    session.close()


@pytest.mark.asyncio
async def test_action_without_lead_fails_softly():
    record = await actions.run_action("CALLBACK", "18:00", None)
    assert record["result"]["ok"] is False


# ----------------------------------------------------------------------------- dialer

def test_voicemail_outcome_is_retried(monkeypatch):
    from voice_agent import dialer as dialer_module
    from voice_agent.dialer import CallQueue

    monkeypatch.setattr(dialer_module, "utcnow", lambda: NOW)
    lead_id = _lead("+919812309004")
    session = SessionLocal()
    job = CallJob(account_id=1, lead_id=lead_id, phone_e164="+919812309004", provider="stub",
                  state="in_progress", attempt=1, max_attempts=3)
    session.add(job)
    session.commit()
    job_id = job.id
    session.close()

    CallQueue().on_call_saved(job_id, None, "voicemail")
    session = SessionLocal()
    job = session.get(CallJob, job_id)
    assert job.state == "retry_scheduled" and job.last_disposition == "voicemail"
    session.close()


# ----------------------------------------------------------------------------- knowledge

def test_small_knowledge_goes_into_the_prompt():
    kb = KnowledgeBase.for_employee({"knowledge_base": "Websites start at ₹25,000."},
                                    [{"name": "pricing.txt", "text": "Mobile apps start at ₹1,50,000."}])
    section = kb.prompt_section()
    assert "₹25,000" in section and "₹1,50,000" in section
    assert kb.relevant("how much is a mobile app") is None  # everything is already in the prompt


def test_large_knowledge_adds_relevant_passages():
    filler = "\n\n".join(f"General company paragraph number {i} about quality and support." for i in range(400))
    special = "Hospital management software includes OPD billing, pharmacy stock and lab reports."
    kb = KnowledgeBase.for_employee(None, [{"name": "big.txt", "text": filler + "\n\n" + special}])
    assert "Hospital" not in kb.prompt_section()
    hint = kb.relevant("Do you have hospital software with pharmacy and billing?")
    assert hint and "pharmacy stock" in hint
    assert kb.relevant("ok") is None


def test_extract_text_from_csv_txt_and_docx():
    assert "Website | 25000" in extract_text("prices.csv", "Service,Price\nWebsite,25000\n".encode())
    assert extract_text("faq.md", "# FAQ\nWe deliver in 4 weeks.".encode()).endswith("4 weeks.")
    import docx
    document = docx.Document()
    document.add_paragraph("CRM software with WhatsApp integration")
    buffer = io.BytesIO()
    document.save(buffer)
    assert "WhatsApp integration" in extract_text("brochure.docx", buffer.getvalue())
    with pytest.raises(ValueError):
        extract_text("virus.exe", b"MZ")


def test_knowledge_upload_api():
    from fastapi.testclient import TestClient
    from main import app
    from models import Employee

    session = SessionLocal()
    employee = Employee(account_id=1, name="KB Test", greeting="Hi", system_prompt="Sell", status="draft")
    session.add(employee)
    session.commit()
    emp_id = employee.id
    session.close()

    client = TestClient(app)
    response = client.post(f"/api/employees/{emp_id}/knowledge",
                           files={"file": ("faq.txt", "Support is 24x7 on WhatsApp.".encode(), "text/plain")})
    assert response.status_code == 200 and response.json()["documents"] == 1
    docs = client.get(f"/api/employees/{emp_id}/knowledge").json()["documents"]
    assert docs[0]["name"] == "faq.txt"
    assert client.post(f"/api/employees/{emp_id}/knowledge",
                       files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 400
    assert client.delete(f"/api/employees/{emp_id}/knowledge/0").status_code == 200
    assert client.get(f"/api/employees/{emp_id}/knowledge").json()["documents"] == []
    assert client.get("/api/analytics/calls").status_code == 200


# ----------------------------------------------------------------------------- session behaviour

class FakeTask:
    def __init__(self):
        self.frames, self.cancelled = [], False

    async def queue_frame(self, frame):
        self.frames.append(frame)

    async def queue_frames(self, frames):
        self.frames.extend(frames)

    async def cancel(self):
        self.cancelled = True


def make_session():
    session = BaseCallSession(lead={"id": None, "name": "Ravi"}, language="te-IN")
    session.task = FakeTask()
    return session


def test_live_rules_include_date_and_lead():
    rules = live_rules({"name": "Ravi"}, "out", NOW)
    assert "Tuesday 03 November 2026, 11:30" in rules and "You called Ravi" in rules
    assert "[CALLBACK: YYYY-MM-DD HH:MM]" in rules
    assert "The customer called you" in live_rules(None, "in", NOW)


@pytest.mark.asyncio
async def test_silence_prompts_then_ends_politely():
    session = make_session()
    await session.on_user_idle()
    assert isinstance(session.task.frames[-1], TTSSpeakFrame)
    assert "వినిపిస్తోందా" in session.task.frames[-1].text
    await session.on_user_idle()
    assert session.hangup_pending and session.end_reason == "no_response"
    session._hangup_fallback.cancel()


@pytest.mark.asyncio
async def test_speaking_resets_the_silence_count():
    session = make_session()
    await session.on_user_idle()
    await session._on_user_text("అవును చెప్పండి", "te-IN")
    await session.on_user_idle()
    assert not session.hangup_pending  # a fresh "can you hear me?", not the goodbye


@pytest.mark.asyncio
async def test_hold_extends_the_silence_timer_until_they_speak():
    import asyncio
    session = make_session()
    hint = session.message_hints("ఒక్క నిమిషం అండి")
    await asyncio.sleep(0)
    assert "take your time" in hint and session.on_hold
    assert isinstance(session.task.frames[-1], UserIdleTimeoutUpdateFrame) and session.task.frames[-1].timeout == 45
    session.message_hints("సరే, చెప్పండి ఇప్పుడు")
    await asyncio.sleep(0)
    assert not session.on_hold and session.task.frames[-1].timeout == 8


@pytest.mark.asyncio
async def test_machine_ends_the_call_and_is_recorded():
    import asyncio
    session = make_session()
    await session.on_machine("voicemail", "Please leave a message after the beep")
    await asyncio.sleep(0)
    assert session.task.cancelled and session.end_reason == "voicemail" and session.ended_by == "machine"
    assert session.analytics(12)["machine"] == "voicemail"


@pytest.mark.asyncio
async def test_call_guard_swallows_machine_transcripts(monkeypatch):
    from pipecat.processors.frame_processor import FrameProcessor

    async def skip(self, frame, direction):
        return None

    monkeypatch.setattr(FrameProcessor, "process_frame", skip)
    detected, passed = [], []

    async def on_machine(kind, text):
        detected.append(kind)

    guard = CallGuard(on_machine)

    async def capture(frame, direction=None):
        passed.append(frame)

    monkeypatch.setattr(guard, "push_frame", capture)
    await guard.process_frame(TranscriptionFrame("Hello, who is this?", "u", "t"), None)
    await guard.process_frame(TranscriptionFrame("For English press 1", "u", "t"), None)
    await guard.process_frame(TranscriptionFrame("anything after", "u", "t"), None)
    assert detected == ["ivr"] and len(passed) == 1

    off = CallGuard(on_machine, enabled=False)
    monkeypatch.setattr(off, "push_frame", capture)
    await off.process_frame(TranscriptionFrame("For English press 1", "u", "t"), None)
    assert len(passed) == 2 and detected == ["ivr"]


def test_phone_recording_is_saved_as_stereo_wav(tmp_path, monkeypatch):
    from voice_agent import session as session_module
    monkeypatch.setattr(session_module, "RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(session_module, "update_call_recording", lambda call_id, url: True)
    session = make_session()
    session._audio = (b"\x01\x00\x02\x00" * 16000, 16000, 2)
    url = session._save_recording(77)
    assert url == "/api/calls/77/recording"
    with wave.open(str(tmp_path / "call_77.wav")) as wav:
        assert wav.getnchannels() == 2 and wav.getframerate() == 16000 and wav.getnframes() == 16000


# ----------------------------------------------------------------------------- safety rules

@pytest.mark.parametrize("spoken,actions,expected", [
    ("Do you need a web app?", [("CALL_COMPLETED", "")], []),
    ("Sending the quote now. Shall we do a demo tomorrow at 11?",
     [("SEND_WHATSAPP", "quotation"), ("CALLBACK", "2026-11-04 11:00")], [("SEND_WHATSAPP", "quotation")]),
    ("I will not call you again. Goodbye!", [("CALL_COMPLETED", "")], [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")]),
    ("आपको दोबारा कॉल नहीं किया जाएगा, अलविदा!", [("CALL_COMPLETED", "")], [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")]),
    ("సరే అండి, మళ్ళీ కాల్ చేయము. సెలవు!", [("CALL_COMPLETED", "")], [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")]),
    ("Our senior lead will call you tomorrow. Bye!", [("CALL_COMPLETED", "")], [("CALL_COMPLETED", "")]),
    ("Okay, bye!", [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")], [("DO_NOT_CALL", ""), ("CALL_COMPLETED", "")]),
])
def test_guard_actions(spoken, actions, expected):
    from voice_agent.conclusion import guard_actions
    assert guard_actions(spoken, actions) == expected


@pytest.mark.parametrize("text,unclear", [
    ("the ... website ... kh kh ... how ...", True), ("[noise] hello", True),
    ("I need a website.", False), ("Hmm... okay", False),
])
def test_unclear_audio_signal(text, unclear):
    assert ("unclear" in caller_signals(text)) is unclear


# ----------------------------------------------------------------------------- booking check

def _booking(intel, actions):
    from types import SimpleNamespace
    from voice_agent.session import BaseCallSession
    fake = SimpleNamespace(actions=actions, session_id="t", BOOKED_STAGES=BaseCallSession.BOOKED_STAGES)
    return BaseCallSession._check_booking(fake, intel)


def test_demo_without_agreed_meeting_stays_follow_up():
    # 6 Nov real call: the customer only said "Hmm", the summary claimed a tentative demo
    out = _booking({"deal_stage": "demo_scheduled", "outcome_label": "meeting_booked", "summary": "Tentative demo."}, [])
    assert out["deal_stage"] == "follow_up" and out["outcome_label"] == "interested_later"
    assert "No demo time was confirmed" in out["summary"]


def test_demo_with_agreed_meeting_is_kept():
    out = _booking({"deal_stage": "demo_scheduled"}, [{"action": "MEETING", "arg": "2026-11-07 11:00"}])
    assert out["deal_stage"] == "demo_scheduled"


def test_greetings_are_not_answers_rule_is_in_the_prompt():
    from voice_agent.session import VOICE_RULES
    assert "are NOT answers" in VOICE_RULES


def test_prompt_says_disclosure_once_and_one_retry_on_not_interested():
    from voice_agent.session import VOICE_RULES
    assert "Never repeat that." in VOICE_RULES
    assert "make one short attempt" in VOICE_RULES and "[DO_NOT_CALL] [CALL_COMPLETED]" in VOICE_RULES
