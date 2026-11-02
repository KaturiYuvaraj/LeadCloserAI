"""
T1 spike: real-time voice agent with Pipecat + Sarvam (streaming STT, LLM, TTS).

Same pipeline for two transports:
  - Browser (WebRTC):  python bot.py                  → open http://localhost:7860/client
  - Exotel phone call: python bot.py --transport exotel  (Exotel Voicebot applet → wss://<host>/ws)

Measures the gap between the caller finishing and the bot starting to speak
for every turn, and logs a per-service breakdown (STT / LLM / TTS time to first byte).
"""

import os
import statistics
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments, SmallWebRTCRunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

from voice_switch import LanguageRouter

# Local .env first, then fall back to the main app's .env (so the key lives in one place)
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
load_dotenv(HERE.parent.parent / "telugu-ai-caller" / ".env", override=False)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "te-IN")          # te-IN | hi-IN | en-IN
VAD_STOP_SECS = float(os.getenv("VAD_STOP_SECS", "0.5"))  # silence that ends the caller's turn
LLM_MODEL = os.getenv("LLM_MODEL", "sarvam-105b-conversations")
STT_MODEL = os.getenv("STT_MODEL", "saaras:v3")
AGENCY = os.getenv("AGENCY_NAME", "S P Associates Software Company")

# Same voices the main app uses (bulbul:v4-flash speaker names)
VOICES = {
    "te-IN": "kavitha_te_conversation",
    "hi-IN": "aditya_hi_sales",
    "en-IN": "simran_en_sales",
}

GREETINGS = {
    "te-IN": f"నమస్కారం అండి! నేను {AGENCY} నుండి మాట్లాడుతున్నాను. ఈ కాల్ రికార్డ్ అవుతోంది, నేను AI అసిస్టెంట్‌ని. మీ వ్యాపారం కోసం వెబ్‌సైట్ లేదా యాప్ గురించి రెండు నిమిషాలు మాట్లాడొచ్చా?",
    "hi-IN": f"नमस्ते जी! मैं {AGENCY} से बात कर रहा हूँ। यह कॉल रिकॉर्ड हो रही है, मैं एक AI असिस्टेंट हूँ। क्या आपके बिज़नेस की वेबसाइट या ऐप के बारे में दो मिनट बात कर सकते हैं?",
    "en-IN": f"Hello! I'm calling from {AGENCY}. This call is recorded and I'm an AI assistant. May I take two minutes to talk about a website or app for your business?",
}

SYSTEM_PROMPT = f"""You are a polite, confident sales closer for {AGENCY}, speaking on a live phone call.
Services: custom websites and SaaS (from ₹25,000), Android and iOS apps (from ₹45,000), AI calling agents and chatbots, billing software.
Goal: understand the customer's need and book a 10-minute demo for tomorrow at 11 AM or 4 PM.

Rules:
- Reply ONLY in the language of the customer's latest message (Telugu, Hindi or English). Never mix two languages in one reply. Switch immediately if they switch.
- Keep every reply to one or two short spoken sentences. No lists, no emojis, no markdown.
- Acknowledge what they said first ("సరేనండి, అర్థమైంది", "जी बिल्कुल", "Got it"), then answer, then ask one question.
- Budget concern: offer milestone payments. "Send on WhatsApp": agree, then ask for the demo slot.
- Never invent prices beyond the starting prices above.
"""


class LatencyStats:
    """Collects user-stopped → bot-started gaps and prints a running summary."""

    def __init__(self):
        self.samples: list[float] = []

    def add(self, seconds: float):
        # The observer starts timing after VAD confirms silence, so add the VAD wait
        total = seconds + VAD_STOP_SECS
        self.samples.append(total)
        logger.info(
            f"⏱  REPLY GAP {total:.2f}s (pipeline {seconds:.2f}s + silence wait {VAD_STOP_SECS:.2f}s) · "
            f"avg {statistics.mean(self.samples):.2f}s over {len(self.samples)} turns"
        )


async def bot(runner_args: RunnerArguments):
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set (spikes/pipecat_voice/.env or telugu-ai-caller/.env)")

    is_phone = not isinstance(runner_args, SmallWebRTCRunnerArguments)

    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
            "exotel": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
        },
    )

    stt = SarvamSTTService(
        api_key=SARVAM_API_KEY,
        settings=SarvamSTTService.Settings(model=STT_MODEL, language="unknown"),
        mode="transcribe",
    )
    llm = SarvamLLMService(
        api_key=SARVAM_API_KEY,
        settings=SarvamLLMService.Settings(model=LLM_MODEL, temperature=0.5, max_tokens=120),
    )
    tts = SarvamTTSService(
        api_key=SARVAM_API_KEY,
        settings=SarvamTTSService.Settings(
            model="bulbul:v4-flash",
            voice=VOICES.get(BOT_LANGUAGE, VOICES["te-IN"]),
            language=BOT_LANGUAGE,
            pace=1.05,
        ),
    )

    greeting = GREETINGS.get(BOT_LANGUAGE, GREETINGS["te-IN"])
    context = LLMContext([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": greeting},
    ])
    context_pair = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=VAD_STOP_SECS)),
        ),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        LanguageRouter(VOICES, initial_language=BOT_LANGUAGE),
        context_pair.user(),
        llm,
        tts,
        transport.output(),
        context_pair.assistant(),
    ])

    latency_observer = UserBotLatencyObserver()
    stats = LatencyStats()

    @latency_observer.event_handler("on_latency_measured")
    async def on_latency(observer, latency_seconds):
        stats.add(latency_seconds)

    @latency_observer.event_handler("on_latency_breakdown")
    async def on_breakdown(observer, breakdown):
        parts = ", ".join(
            f"{m.processor.split('#')[0]} {m.duration_secs * 1000:.0f}ms"
            for m in getattr(breakdown, "ttfb", []) or []
        )
        if parts:
            logger.info(f"   breakdown (time to first byte): {parts}")

    params = PipelineParams(enable_metrics=True, enable_usage_metrics=True)
    if is_phone:
        # Exotel Voicebot streams 8 kHz mono PCM
        params = PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
        )

    task = PipelineTask(pipeline, params=params, observers=[latency_observer])

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        logger.info(f"Caller connected ({'phone' if is_phone else 'browser'}) · language {BOT_LANGUAGE} · STT {STT_MODEL}")
        # Speak the greeting straight away (no LLM round-trip)
        await task.queue_frames([TTSSpeakFrame(greeting)])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        if stats.samples:
            logger.info(
                f"Call ended · {len(stats.samples)} turns · reply gap avg {statistics.mean(stats.samples):.2f}s · "
                f"best {min(stats.samples):.2f}s · worst {max(stats.samples):.2f}s"
            )
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
