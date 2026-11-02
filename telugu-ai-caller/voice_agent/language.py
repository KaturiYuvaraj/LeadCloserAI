"""
Language routing for multilingual calls.

For every final caller transcription the router:
  1. detects the caller's language from the transcript (Telugu / Devanagari / Latin script),
  2. reports the clean text to the session (for the stored transcript and the live UI),
  3. appends a short instruction so the LLM replies only in that language
     (without it the model drifts back to the call's opening language), and
  4. if the language changed, pushes a TTSUpdateSettingsFrame so Sarvam speaks the
     reply with the matching voice. The frame travels ahead of the transcription,
     so the voice is switched before the reply reaches TTS (Sarvam resends its
     config; no reconnect).
"""

from typing import Awaitable, Callable, Optional

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame, TTSUpdateSettingsFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.sarvam.tts import SarvamTTSService

# bulbul:v4-flash speakers, same voices as the classic engine
VOICES = {
    "te-IN": "kavitha_te_conversation",
    "hi-IN": "aditya_hi_sales",
    "en-IN": "simran_en_sales",
}

LANGUAGE_NAMES = {"te-IN": "Telugu", "hi-IN": "Hindi", "en-IN": "English"}

# Romanized words that mark Hinglish / Tenglish written in Latin script
HINDI_HINTS = ("aap", "hai", "nahi", "kya", "kitna", "chahiye", "theek", "bilkul", "haan", "accha")
TELUGU_HINTS = ("andi", "meeku", "kavali", "entha", "ledu", "avunu", "cheppandi", "garu", "chala")


def detect_language(text: str) -> Optional[str]:
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


UserTextCallback = Callable[[str, str], Awaitable[None]]


class LanguageRouter(FrameProcessor):
    """Keeps the LLM reply language and the TTS voice matched to the caller's language."""

    def __init__(self, initial_language: str, on_user_text: Optional[UserTextCallback] = None, **kwargs):
        super().__init__(**kwargs)
        self._current = initial_language if initial_language in VOICES else "te-IN"
        self._on_user_text = on_user_text

    @property
    def current_language(self) -> str:
        return self._current

    def prepare(self, text: str) -> tuple[str, Optional[TTSUpdateSettingsFrame]]:
        """
        Detect the language of a caller message. Returns the text annotated with the
        reply-language instruction and, when the language changed, the frame that
        switches the TTS voice.
        """
        switch_frame = None
        language = detect_language(text) or self._current
        if language != self._current and language in VOICES:
            logger.info(f"🗣  Voice switch {self._current} → {language} ({VOICES[language]})")
            self._current = language
            switch_frame = TTSUpdateSettingsFrame(
                delta=SarvamTTSService.Settings(voice=VOICES[language], language=language)
            )
        name = LANGUAGE_NAMES.get(self._current, "the customer's language")
        return f"{text.strip()}\n(Reply only in {name}.)", switch_frame

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            clean_text = frame.text.strip()
            annotated, switch_frame = self.prepare(clean_text)
            if self._on_user_text:
                await self._on_user_text(clean_text, self._current)
            if switch_frame:
                await self.push_frame(switch_frame, direction)
            frame.text = annotated

        await self.push_frame(frame, direction)
