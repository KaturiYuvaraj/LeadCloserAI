"""
Language routing for multilingual calls.

Sits between STT and the user context aggregator. For every final transcription:
  1. detects the caller's language from the transcript (Telugu / Devanagari / Latin script),
  2. appends a short instruction so the LLM replies only in that language
     (without it, the model drifts back to the call's opening language), and
  3. if the language changed, pushes a TTSUpdateSettingsFrame so Sarvam speaks the
     reply with the matching voice. The frame travels ahead of the transcription,
     so the voice is switched before the reply text reaches TTS. Sarvam applies a
     voice change by resending its config (no reconnect).
"""

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame, TTSUpdateSettingsFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.sarvam.tts import SarvamTTSService

# Romanized words that mark Hinglish / Tenglish written in Latin script
HINDI_HINTS = ("aap", "hai", "nahi", "kya", "kitna", "chahiye", "theek", "bilkul", "haan", "accha")
TELUGU_HINTS = ("andi", "meeku", "kavali", "entha", "ledu", "avunu", "cheppandi", "garu", "chala")

LANGUAGE_NAMES = {"te-IN": "Telugu", "hi-IN": "Hindi", "en-IN": "English"}


def detect_language(text: str) -> str | None:
    """Return te-IN, hi-IN or en-IN for the given text, or None if undecidable."""
    telugu = sum(1 for ch in text if 0x0C00 <= ord(ch) <= 0x0C7F)
    devanagari = sum(1 for ch in text if 0x0900 <= ord(ch) <= 0x097F)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())

    if telugu or devanagari:
        return "te-IN" if telugu >= devanagari else "hi-IN"
    if latin >= 4:
        words = [w.strip(",.?!") for w in text.lower().split()]
        hi = sum(1 for w in words if w in HINDI_HINTS)
        te = sum(1 for w in words if w in TELUGU_HINTS)
        if hi > te:
            return "hi-IN"
        if te > hi:
            return "te-IN"
        return "en-IN"
    return None


class LanguageRouter(FrameProcessor):
    """Keeps the LLM reply language and the TTS voice matched to the caller's language."""

    def __init__(self, voices: dict[str, str], initial_language: str, **kwargs):
        super().__init__(**kwargs)
        self._voices = voices
        self._current = initial_language

    @property
    def current_language(self) -> str:
        return self._current

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            language = detect_language(frame.text) or self._current
            if language != self._current and language in self._voices:
                logger.info(f"🗣  Voice switch {self._current} → {language} ({self._voices[language]})")
                self._current = language
                await self.push_frame(
                    TTSUpdateSettingsFrame(
                        delta=SarvamTTSService.Settings(voice=self._voices[language], language=language)
                    ),
                    direction,
                )
            name = LANGUAGE_NAMES.get(self._current, "the customer's language")
            frame.text = f"{frame.text.strip()}\n(Reply only in {name}.)"

        await self.push_frame(frame, direction)
