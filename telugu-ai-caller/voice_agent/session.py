"""
Real-time call sessions: one shared Pipecat conversation core, two transports.

Pipeline (same for both):
  audio in → Sarvam streaming STT → LanguageRouter → user context (Silero VAD)
  → Sarvam LLM → reply tap → Sarvam streaming TTS → audio out → assistant context

- WebCallSession:   dashboard browser calls over WebRTC. Live UI events go to the
                    browser on the data channel as JSON with an `lc` field.
- PhoneCallSession: phone calls over the Exotel Voicebot WebSocket (8 kHz PCM).
                    The lead comes from the `lead_id` custom parameter (outbound)
                    or is matched by the caller's number (inbound).
- VobizCallSession: phone calls over a Vobiz bidirectional stream (16 kHz Linear16),
                    including numbers rented from Sarvam (powered by Vobiz).

When a call ends the transcript is summarized with the existing sales agent and
saved through `save_call_record`, exactly like the classic engine.
"""

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMMessagesAppendFrame,
    LLMTextFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from config import SARVAM_API_KEY
from database import clean_phone, get_all_leads, get_lead_by_id, save_call_record
from services.language_utils import detect_language as detect_text_language
from services.sales_agent import sales_agent
from voice_agent.conclusion import CallConclusionFilter
from voice_agent.language import VOICES, LanguageRouter
from voice_agent.vobiz import VOBIZ_SAMPLE_RATE, VobizFrameSerializer

STT_MODEL = os.getenv("VOICE_STT_MODEL", "saaras:v3")
LLM_MODEL = os.getenv("VOICE_LLM_MODEL", "sarvam-105b-conversations")
TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "bulbul:v4-flash")
PHONE_SAMPLE_RATE = 8000  # Exotel Voicebot streams 8 kHz mono PCM

DISCLOSURE = {
    "te-IN": "ఈ కాల్ రికార్డ్ అవుతోంది, నేను AI అసిస్టెంట్‌ని.",
    "hi-IN": "यह कॉल रिकॉर्ड हो रही है, मैं एक AI असिस्टेंट हूँ।",
    "en-IN": "This call is recorded and I'm an AI assistant.",
    "ta-IN": "இந்த அழைப்பு பதிவு செய்யப்படுகிறது, நான் ஒரு AI உதவியாளர்.",
    "kn-IN": "ಈ ಕರೆಯನ್ನು ರೆಕಾರ್ಡ್ ಮಾಡಲಾಗುತ್ತಿದೆ, ನಾನು AI ಸಹಾಯಕ.",
    "ml-IN": "ഈ കോൾ റെക്കോർഡ് ചെയ്യപ്പെടുന്നു, ഞാൻ ഒരു AI അസിസ്റ്റന്റാണ്.",
}

VOICE_RULES = """
LIVE PHONE CONVERSATION RULES (override anything above that conflicts):
- You are speaking out loud. Reply in one or two short spoken sentences. No lists, no emojis, no markdown.
- Reply ONLY in the language of the customer's latest message. Never mix two languages in one reply.
- Never invent prices beyond the company's starting prices.
"""


def wait_ms_to_vad_stop_secs(wait_ms: Optional[int]) -> float:
    """
    Map the dashboard's "Reply wait" setting to Silero VAD stop time.
    Fast 700 → 0.3s · Normal 900 → 0.5s · Patient 1300 → 0.9s.
    """
    try:
        ms = int(wait_ms) if wait_ms is not None else 900
    except (TypeError, ValueError):
        ms = 900
    return round(min(1.2, max(0.3, (ms - 400) / 1000)), 2)


def as_text(value: Any) -> str:
    """
    The summary LLM sometimes returns lists (e.g. several requirements) or None where
    the database expects text; join/serialize them so the call is never lost on save.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(as_text(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def find_lead_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Match a caller's number to an existing lead (last 10 digits, so +91/0 prefixes don't matter)."""
    digits = "".join(ch for ch in clean_phone(phone or "") if ch.isdigit())[-10:]
    if len(digits) < 10:
        return None
    for lead in get_all_leads():
        lead_digits = "".join(ch for ch in str(lead.get("phone") or "") if ch.isdigit())[-10:]
        if lead_digits == digits:
            return lead
    return None


def parse_custom_parameters(raw: Any) -> Dict[str, str]:
    """Exotel custom parameters may arrive as a dict or as a 'key=value&key2=value2' string."""
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.startswith("{"):
            try:
                return {str(k): str(v) for k, v in json.loads(text).items()}
            except ValueError:
                pass
        return {k: v[0] for k, v in parse_qs(text.lstrip("?")).items() if v}
    return {}


class ReplyTap(FrameProcessor):
    """Collects each streamed LLM reply into one text and reports it when complete."""

    def __init__(self, on_reply, **kwargs):
        super().__init__(**kwargs)
        self._on_reply = on_reply
        self._parts: List[str] = []
        self._active = False

    async def _finish(self, interrupted: bool):
        text = "".join(self._parts).strip()
        self._parts = []
        self._active = False
        if text:
            await self._on_reply(text, interrupted)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self._parts = []
            self._active = True
        elif isinstance(frame, LLMTextFrame) and self._active:
            self._parts.append(frame.text)
        elif isinstance(frame, LLMFullResponseEndFrame) and self._active:
            await self._finish(interrupted=False)
        elif isinstance(frame, InterruptionFrame) and self._active:
            await self._finish(interrupted=True)
        await self.push_frame(frame, direction)


class SpeakingObserver(BaseObserver):
    """Turns speaking frames into a single state-change event for the UI."""

    def __init__(self, session: "BaseCallSession", **kwargs):
        super().__init__(**kwargs)
        self._session = session
        self._bot = False
        self._user = False

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame
        if isinstance(frame, BotStartedSpeakingFrame) and not self._bot:
            self._bot = True
            self._session.send_event("speaking", who="bot", active=True)
        elif isinstance(frame, BotStoppedSpeakingFrame) and self._bot:
            self._bot = False
            self._session.send_event("speaking", who="bot", active=False)
            await self._session.on_bot_stopped_speaking()
        elif isinstance(frame, UserStartedSpeakingFrame) and not self._user:
            self._user = True
            self._session.send_event("speaking", who="user", active=True)
        elif isinstance(frame, UserStoppedSpeakingFrame) and self._user:
            self._user = False
            self._session.send_event("speaking", who="user", active=False)


class BaseCallSession:
    """Conversation core shared by browser and phone calls."""

    call_type = "web"

    def __init__(self, lead: Optional[Dict[str, Any]] = None, language: Optional[str] = None,
                 wait_ms: Optional[int] = None):
        self.session_id = uuid.uuid4().hex
        self.lead = lead
        self.lead_id = lead.get("id") if lead else None
        preferred = language or (lead or {}).get("preferred_language") or "te-IN"
        self.language = preferred if preferred in VOICES else "te-IN"
        self.vad_stop_secs = wait_ms_to_vad_stop_secs(wait_ms)

        self.transcript: List[Dict[str, str]] = []
        self.latencies: List[float] = []
        self.started_at = time.time()
        self.ended_by = "system"
        self.task: Optional[PipelineTask] = None
        self.router: Optional[LanguageRouter] = None
        self.result: Optional[Dict[str, Any]] = None
        self.done = asyncio.Event()
        self.hangup_pending = False
        self._hangup_fallback: Optional[asyncio.Task] = None
        self.job_id: Optional[int] = None  # outbound dialer job (voice_agent/dialer.py), if any

    # ------------------------------------------------------------------ hooks for subclasses
    def send_event(self, kind: str, **payload):
        """Live UI event. Browser calls send it on the data channel; phone calls only log."""
        logger.trace(f"[{self.session_id}] {kind} {payload}")

    def create_transport(self) -> BaseTransport:
        raise NotImplementedError

    def pipeline_params(self) -> PipelineParams:
        return PipelineParams(enable_metrics=True, enable_usage_metrics=True)

    def register_transport_handlers(self, transport: BaseTransport):
        """Extra transport event handlers (e.g. browser app messages)."""

    def phone_number(self) -> str:
        return (self.lead or {}).get("phone") or "Web Browser"

    # ------------------------------------------------------------------ transcript
    async def _on_user_text(self, text: str, language: str):
        self.transcript.append({"role": "user", "content": text})
        self.send_event("transcript", role="user", text=text, language=language)
        self.send_event("status", text="🧠 Thinking…")

    async def _on_reply(self, text: str, interrupted: bool):
        self.transcript.append({"role": "assistant", "content": text})
        self.send_event(
            "transcript", role="assistant", text=text,
            language=detect_text_language(text), interrupted=interrupted,
        )

    # ------------------------------------------------------------------ prompt
    async def _build_prompt_and_greeting(self) -> tuple[str, str]:
        system_prompt = sales_agent._build_system_prompt(self.lead) + VOICE_RULES
        greeting = await sales_agent.get_initial_greeting(self.lead_id, language_code=self.language)
        greeting = f"{greeting} {DISCLOSURE.get(self.language, DISCLOSURE['en-IN'])}"
        return system_prompt, greeting

    # ------------------------------------------------------------------ controls
    async def handle_text_input(self, text: str):
        """Typed reply (dashboard text box): same path as a spoken turn."""
        text = (text or "").strip()
        if not text or not self.task or not self.router:
            return
        annotated, switch_frame = self.router.prepare(text)
        await self._on_user_text(text, self.router.current_language)
        frames: List[Frame] = []
        if switch_frame:
            frames.append(switch_frame)
        frames.append(LLMMessagesAppendFrame(messages=[{"role": "user", "content": annotated}], run_llm=True))
        await self.task.queue_frames(frames)

    async def hangup(self):
        self.ended_by = "caller"
        if self.task:
            await self.task.cancel()

    # ------------------------------------------------------------------ AI ends the call
    async def _on_conversation_concluded(self):
        """The AI said goodbye ([CALL_COMPLETED]): end the call once the goodbye has been spoken."""
        if self.hangup_pending:
            return
        logger.info(f"{self.call_type.title()} call {self.session_id}: AI concluded the conversation")
        self.hangup_pending = True
        self.send_event("status", text="👋 Wrapping up the call…")
        # Safety net in case the "bot stopped speaking" signal never arrives
        self._hangup_fallback = asyncio.create_task(self._end_after(15.0))

    async def on_bot_stopped_speaking(self):
        if self.hangup_pending:
            await self._end_after(0.8)  # short pause after the goodbye

    async def _end_after(self, delay: float):
        await asyncio.sleep(delay)
        if not self.task or self.done.is_set() or self.ended_by == "agent":
            return
        self.ended_by = "agent"
        self.send_event("call_ending", reason="conversation_completed")
        await self.task.queue_frame(EndFrame())

    # ------------------------------------------------------------------ run
    async def run(self):
        try:
            await self._run_pipeline()
        except Exception as e:
            logger.exception(f"Call session {self.session_id} failed: {e}")
            self.send_event("status", text="Connection problem — call ended.")
        finally:
            await self._finish_call()

    async def _run_pipeline(self):
        system_prompt, greeting = await self._build_prompt_and_greeting()
        transport = self.create_transport()

        stt = SarvamSTTService(
            api_key=SARVAM_API_KEY,
            settings=SarvamSTTService.Settings(model=STT_MODEL, language="unknown"),
            mode="transcribe",
        )
        llm = SarvamLLMService(
            api_key=SARVAM_API_KEY,
            settings=SarvamLLMService.Settings(model=LLM_MODEL, temperature=0.5, max_tokens=140),
        )
        tts = SarvamTTSService(
            api_key=SARVAM_API_KEY,
            settings=SarvamTTSService.Settings(
                model=TTS_MODEL, voice=VOICES[self.language], language=self.language, pace=1.05,
            ),
        )

        self.router = LanguageRouter(self.language, on_user_text=self._on_user_text)
        context = LLMContext([
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": greeting},
        ])
        context_pair = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=self.vad_stop_secs)),
            ),
        )

        pipeline = Pipeline([
            transport.input(),
            stt,
            self.router,
            context_pair.user(),
            llm,
            CallConclusionFilter(self._on_conversation_concluded),
            ReplyTap(self._on_reply),
            tts,
            transport.output(),
            context_pair.assistant(),
        ])

        latency_observer = UserBotLatencyObserver()

        @latency_observer.event_handler("on_latency_measured")
        async def on_latency(observer, seconds):
            total = seconds + self.vad_stop_secs
            self.latencies.append(total)
            self.send_event("latency", total_ms=int(total * 1000), pipeline_ms=int(seconds * 1000))

        @latency_observer.event_handler("on_latency_breakdown")
        async def on_breakdown(observer, breakdown):
            parts = {}
            for metric in getattr(breakdown, "ttfb", []) or []:
                name = metric.processor.split("#")[0].replace("Sarvam", "").replace("Service", "").lower()
                parts[name] = int(metric.duration_secs * 1000)
            if parts:
                self.send_event("breakdown", **parts)

        self.task = PipelineTask(
            pipeline,
            params=self.pipeline_params(),
            observers=[latency_observer, SpeakingObserver(self)],
        )

        @transport.event_handler("on_client_connected")
        async def on_connected(transport, client):
            logger.info(
                f"{self.call_type.title()} call {self.session_id} connected · lead {self.lead_id} · {self.language}"
            )
            self.started_at = time.time()
            self.transcript.append({"role": "assistant", "content": greeting})
            self.send_event("transcript", role="assistant", text=greeting, language=self.language)
            await self.task.queue_frames([TTSSpeakFrame(greeting)])

        @transport.event_handler("on_client_disconnected")
        async def on_disconnected(transport, client):
            if self.ended_by == "system":
                self.ended_by = "caller"
            if self._hangup_fallback:
                self._hangup_fallback.cancel()
            await self.task.cancel()

        self.register_transport_handlers(transport)
        await PipelineRunner(handle_sigint=False).run(self.task)

    # ------------------------------------------------------------------ after the call
    def extra_result_fields(self) -> Dict[str, Any]:
        return {}

    async def _finish_call(self):
        duration = int(time.time() - self.started_at)
        avg_latency = round(sum(self.latencies) / len(self.latencies), 2) if self.latencies else None
        logger.info(
            f"{self.call_type.title()} call {self.session_id} ended by {self.ended_by} · {duration}s · "
            f"{len(self.latencies)} turns · avg reply gap {avg_latency}s"
        )

        try:
            intel = await sales_agent.extract_call_intelligence(self.transcript)
        except Exception as e:
            logger.error(f"Intelligence extraction failed: {e}")
            intel = {"summary": "Completed call.", "sentiment": "neutral", "deal_stage": "qualifying"}
        intel = {key: as_text(value) for key, value in (intel or {}).items()}

        call_record = {
            "lead_id": self.lead_id,
            "call_type": self.call_type,
            "phone_number": self.phone_number(),
            "duration_seconds": duration,
            "status": "completed",
            "summary": intel.get("summary", ""),
            "sentiment": intel.get("sentiment", "neutral"),
            "deal_stage": intel.get("deal_stage", "qualifying"),
            "extracted_budget": intel.get("extracted_budget", ""),
            "extracted_timeline": intel.get("extracted_timeline", ""),
            "extracted_requirements": intel.get("extracted_requirements", ""),
            "objections_raised": intel.get("objections_raised", ""),
            "action_items": intel.get("action_items", ""),
            "transcript": json.dumps(self.transcript, ensure_ascii=False),
            **self.extra_result_fields(),
        }

        try:
            call_id = await asyncio.to_thread(save_call_record, call_record)
        except Exception as e:
            logger.error(f"Failed to save call record: {e}")
            call_id = None

        self.result = {
            "call_id": call_id,
            "intelligence": intel,
            "duration": duration,
            "turns": len(self.latencies),
            "avg_reply_gap_s": avg_latency,
            "ended_by": self.ended_by,
        }
        if self.job_id:
            from voice_agent.dialer import call_queue
            await asyncio.to_thread(call_queue.on_call_saved, self.job_id, call_id,
                                    intel.get("deal_stage") or "completed")
        self.send_event("call_summary", **self.result)
        self.done.set()


class WebCallSession(BaseCallSession):
    """Dashboard browser call over WebRTC."""

    call_type = "web"

    def __init__(self, connection: SmallWebRTCConnection, lead_id: Optional[int] = None,
                 language: Optional[str] = None, wait_ms: Optional[int] = None):
        super().__init__(get_lead_by_id(lead_id) if lead_id else None, language, wait_ms)
        self.connection = connection

    def send_event(self, kind: str, **payload):
        try:
            self.connection.send_app_message({"lc": kind, **payload})
        except Exception as e:  # data channel not open yet / closed
            logger.debug(f"UI event '{kind}' not sent: {e}")

    def create_transport(self) -> BaseTransport:
        return SmallWebRTCTransport(
            webrtc_connection=self.connection,
            params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        )

    def register_transport_handlers(self, transport: BaseTransport):
        @transport.event_handler("on_app_message")
        async def on_app_message(transport, message, sender=None):
            payload = message if isinstance(message, dict) else {}
            if isinstance(message, str):
                try:
                    payload = json.loads(message)
                except ValueError:
                    payload = {}
            kind = payload.get("lc")
            if kind == "text_input":
                await self.handle_text_input(payload.get("text", ""))
            elif kind == "hangup":
                await self.hangup()


class PhoneCallSession(BaseCallSession):
    """Phone call over the Exotel Voicebot WebSocket (bidirectional 8 kHz PCM)."""

    call_type = "phone"
    provider = "exotel"

    def __init__(self, websocket, call_data: Dict[str, Any], query_params: Optional[Dict[str, str]] = None):
        custom = parse_custom_parameters(call_data.get("custom_parameters"))
        params = {**(query_params or {}), **custom}

        lead = None
        lead_id = params.get("lead_id")
        if lead_id and str(lead_id).isdigit():
            lead = get_lead_by_id(int(lead_id))
        caller = str(call_data.get("from") or "")
        callee = str(call_data.get("to") or "")
        self.direction = "out" if lead else "in"
        if not lead:
            lead = find_lead_by_phone(caller)

        super().__init__(lead, params.get("lang"), params.get("wait_ms"))
        self.websocket = websocket
        self.stream_sid = str(call_data.get("stream_id") or "")
        self.call_sid = str(call_data.get("call_id") or "")
        self.caller = caller
        self.callee = callee
        job_id = str(params.get("job_id") or "")
        self.job_id = int(job_id) if job_id.isdigit() else None

    def create_transport(self) -> BaseTransport:
        serializer = ExotelFrameSerializer(stream_sid=self.stream_sid, call_sid=self.call_sid)
        return FastAPIWebsocketTransport(
            websocket=self.websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=serializer,
            ),
        )

    def pipeline_params(self) -> PipelineParams:
        return PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=PHONE_SAMPLE_RATE,
            audio_out_sample_rate=PHONE_SAMPLE_RATE,
        )

    def phone_number(self) -> str:
        if self.direction == "out":
            return (self.lead or {}).get("phone") or self.callee
        return self.caller or (self.lead or {}).get("phone") or ""

    def extra_result_fields(self) -> Dict[str, Any]:
        return {"call_sid": self.call_sid}


class VobizCallSession(PhoneCallSession):
    """Phone call over a Vobiz bidirectional stream (also Sarvam-rented numbers)."""

    provider = "vobiz"

    def __init__(self, websocket, call_data: Dict[str, Any], query_params: Optional[Dict[str, str]] = None):
        super().__init__(websocket, call_data, query_params)
        self.inbound_encoding = call_data.get("encoding", "l16")
        self.inbound_sample_rate = int(call_data.get("sample_rate") or VOBIZ_SAMPLE_RATE)

    def create_transport(self) -> BaseTransport:
        serializer = VobizFrameSerializer(
            stream_id=self.stream_sid,
            inbound_encoding=self.inbound_encoding,
            inbound_sample_rate=self.inbound_sample_rate,
        )
        return FastAPIWebsocketTransport(
            websocket=self.websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=serializer,
            ),
        )

    def pipeline_params(self) -> PipelineParams:
        return PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=VOBIZ_SAMPLE_RATE,
            audio_out_sample_rate=VOBIZ_SAMPLE_RATE,
        )
