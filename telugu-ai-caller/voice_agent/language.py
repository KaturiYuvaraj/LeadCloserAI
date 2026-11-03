"""
Language routing for multilingual calls.

For every final caller transcription the router:
  1. detects the caller's language from the transcript (Telugu / Devanagari / Tamil / Kannada / Malayalam / Latin script),
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

from pipecat.frames.frames import Frame, TranscriptionFrame
try:
    from pipecat.frames.frames import TTSUpdateSettingsFrame  # type: ignore
except ImportError:
    class TTSUpdateSettingsFrame(Frame):  # type: ignore
        def __init__(self, delta=None):
            self.delta = delta

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
try:
    from pipecat.services.sarvam.tts import SarvamTTSService  # type: ignore
except ImportError:
    class SarvamTTSService:  # type: ignore
        class Settings:
            def __init__(self, voice=None, language=None):
                self.voice = voice
                self.language = language

# bulbul:v4-flash speakers for all supported languages
VOICES = {
    "te-IN": "kavitha_te_conversation",
    "hi-IN": "aditya_hi_sales",
    "en-IN": "simran_en_sales",
    "ta-IN": "meera_ta_conversation",
    "kn-IN": "shreya_kn_conversation",
    "ml-IN": "arya_ml_conversation",
}

LANGUAGE_NAMES = {
    "te-IN": "Telugu",
    "hi-IN": "Hindi",
    "en-IN": "English",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
}

# Romanized words that mark code-switching written in Latin script
HINDI_HINTS = ("aap", "hai", "nahi", "kya", "kitna", "chahiye", "theek", "bilkul", "haan", "accha")
TELUGU_HINTS = ("andi", "meeku", "kavali", "entha", "ledu", "avunu", "cheppandi", "garu", "chala")
TAMIL_HINTS = ("vanakkam", "enga", "romba", "nalla", "illai", "ama", "sollunga", "eppadi", "ungalukku", "thevai")
KANNADA_HINTS = ("namaskara", "beku", "illa", "hege", "nimge", "enu", "tumba", "heli", "yavaga", "kodi")
MALAYALAM_HINTS = ("namaskaram", "venam", "illa", "engane", "ningalkku", "entha", "valare", "parayu", "ariyaam", "undu")


def detect_language(text: str) -> Optional[str]:
    """Return te-IN, hi-IN, en-IN, ta-IN, kn-IN, or ml-IN for the given text, or None if undecidable."""
    devanagari = sum(1 for ch in text if 0x0900 <= ord(ch) <= 0x097F)
    tamil = sum(1 for ch in text if 0x0B80 <= ord(ch) <= 0x0BFF)
    telugu = sum(1 for ch in text if 0x0C00 <= ord(ch) <= 0x0C7F)
    kannada = sum(1 for ch in text if 0x0C80 <= ord(ch) <= 0x0CFF)
    malayalam = sum(1 for ch in text if 0x0D00 <= ord(ch) <= 0x0D7F)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())

    native_counts = {
        "te-IN": telugu,
        "hi-IN": devanagari,
        "ta-IN": tamil,
        "kn-IN": kannada,
        "ml-IN": malayalam,
    }
    max_native_lang, max_native_count = max(native_counts.items(), key=lambda item: item[1])
    if max_native_count > 0:
        return max_native_lang

    if latin >= 4:
        words = [w.strip(",.?!") for w in text.lower().split()]
        scores = {
            "hi-IN": sum(1 for w in words if w in HINDI_HINTS),
            "te-IN": sum(1 for w in words if w in TELUGU_HINTS),
            "ta-IN": sum(1 for w in words if w in TAMIL_HINTS),
            "kn-IN": sum(1 for w in words if w in KANNADA_HINTS),
            "ml-IN": sum(1 for w in words if w in MALAYALAM_HINTS),
        }
        best_lang, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score > 0:
            return best_lang
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
