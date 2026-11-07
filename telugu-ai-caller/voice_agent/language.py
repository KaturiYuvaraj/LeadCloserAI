"""
Language routing for multilingual calls with robust verification and human pacing.

For every final caller transcription the router:
  1. detects the caller's language from the transcript (Telugu / Devanagari / Tamil / Kannada / Malayalam / Latin script),
  2. verifies language shifts carefully: enforces a strict 2-3 check verification rule (or explicit caller request)
     so isolated words, filler phrases, or English loanwords never trigger premature switching,
  3. reports the clean text to the session (for the stored transcript and live UI),
  4. instructs the LLM to reply only in the verified language with natural human conversational empathy, and
  5. pushes a TTSUpdateSettingsFrame to Sarvam so the voice matches the verified language seamlessly.
"""

from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable, Optional, Set

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
    "hi-IN": "kavya_hi_conversational",  # female, to match the agent Shreya
    "en-IN": "simran_en_sales",
    "ta-IN": "kavitha_te_conversation",
    "kn-IN": "chaitra_kn_conversation",
    "ml-IN": "kavitha_te_conversation",
}

LANGUAGE_NAMES = {
    "te-IN": "Telugu",
    "hi-IN": "Hindi",
    "en-IN": "English",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
}

# Common English technical, business, and conversational loanwords in Indian phone calls.
# These words appearing in a conversation do NOT indicate a switch to English.
COMMON_INDIAN_LOANWORDS: Set[str] = {
    "hello", "hi", "hey", "sir", "madam", "madame", "ok", "okay", "yes", "yeah", "yep",
    "no", "nope", "website", "web", "site", "app", "mobile", "application", "software",
    "demo", "price", "cost", "charges", "quote", "quotation", "rate", "rates", "company",
    "business", "meeting", "morning", "evening", "tomorrow", "today", "time", "date",
    "details", "whatsapp", "number", "call", "send", "message", "package", "plan",
    "features", "crm", "sales", "client", "problem", "solution", "billing", "gst",
    "online", "link", "team", "lead", "thanks", "thank", "you", "service", "services",
    "project", "work", "office", "system", "portal"
}

# Explicit language switch command patterns (caller directly requests language change)
EXPLICIT_LANGUAGE_PATTERNS = {
    "en-IN": [
        r"\b(speak|talk|converse)\s+in\s+english\b",
        r"\benglish\s+(please|lo|me|la|dalli|il)\b",
        r"\bcan\s+(we|you)\s+(speak|talk)\s+in\s+english\b",
        r"\bin\s+english\b",
        r"\bplease\s+(talk|speak)\s+in\s+english\b",
    ],
    "te-IN": [
        r"\b(telugu\s*lo|తెలుగులో)\s*(matlad|chepp|pes|bol)",
        r"\btelugu\s+(please|lo|andi|lo\s+cheppandi)\b",
        r"\b(speak|talk)\s+in\s+telugu\b",
        r"\bతెలుగులో\s*(మాట్లాడండి|చెప్పండి|మాట్లాడగలరా)\b",
    ],
    "hi-IN": [
        r"\b(hindi\s*me|हिंदी\s*में)\s*(bol|baat|chepp)",
        r"\bhindi\s+(please|me|bhai|me\s+bolo|me\s+baat)\b",
        r"\b(speak|talk)\s+in\s+hindi\b",
        r"\bहिंदी\s+में\s*(बोलिए|बात\s+करें|बताइए)\b",
    ],
    "ta-IN": [
        r"\b(tamil\s*la|தமிழில்)\s*(pesu|sol)",
        r"\btamil\s+please\b",
        r"\b(speak|talk)\s+in\s+tamil\b",
        r"\bதமிழில்\s*(பேசுங்கள்|சொல்லுங்கள்)\b",
    ],
    "kn-IN": [
        r"\b(kannada\s*dalli|ಕನ್ನಡದಲ್ಲಿ)\s*(matad|heli)",
        r"\bkannada\s+please\b",
        r"\b(speak|talk)\s+in\s+kannada\b",
        r"\bಕನ್ನಡದಲ್ಲಿ\s*(ಮಾತನಾಡಿ|ಹೇಳಿ)\b",
    ],
    "ml-IN": [
        r"\b(malayalam\s*il|മലയാളത്തിൽ)\s*(samsarik|paray)",
        r"\bmalayalam\s+please\b",
        r"\b(speak|talk)\s+in\s+malayalam\b",
        r"\bമലയാളത്തിൽ\s*(സംസാരിക്കൂ|പറയൂ)\b",
    ],
}

# In Indian scripts \\b doesn't work next to vowel signs, so the patterns above can miss. "<language> in"
# written in that language's own script is a request on its own ("हिंदी में बात कीजिए", "తెలుగులో మాట్లాడండి").
NATIVE_LANGUAGE_REQUESTS = {
    "te-IN": r"తెలుగు\s*లో", "hi-IN": r"हिंदी\s*में|हिन्दी\s*में", "ta-IN": r"தமிழில்",
    "kn-IN": r"ಕನ್ನಡದಲ್ಲಿ", "ml-IN": r"മലയാളത്തിൽ",
}
_EXPLICIT_REGEXES = {
    lang: [re.compile(p, re.IGNORECASE) for p in patterns + [NATIVE_LANGUAGE_REQUESTS.get(lang, r"(?!x)x")]]
    for lang, patterns in EXPLICIT_LANGUAGE_PATTERNS.items()
}


def detect_explicit_language_request(text: str) -> Optional[str]:
    """Detect if caller explicitly asked to switch language (e.g. 'Can you speak in English?')."""
    if not text:
        return None
    for lang, regex_list in _EXPLICIT_REGEXES.items():
        if any(r.search(text) for r in regex_list):
            return lang
    return None


# Romanized words that mark code-switching written in Latin script
HINDI_HINTS = ("aap", "hai", "nahi", "kya", "kitna", "chahiye", "theek", "bilkul", "haan", "accha", "bataiye", "karenge")
TELUGU_HINTS = ("andi", "meeku", "kavali", "entha", "ledu", "avunu", "cheppandi", "garu", "chala", "ela", "eppudu", "manchi")
TAMIL_HINTS = ("vanakkam", "enga", "romba", "nalla", "illai", "ama", "sollunga", "eppadi", "ungalukku", "thevai", "pesalam")
KANNADA_HINTS = ("namaskara", "beku", "illa", "hege", "nimge", "enu", "tumba", "heli", "yavaga", "kodi", "chennagide")
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
        words = [w.strip(",.?!").lower() for w in text.split()]
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

        # Exclude common loan words before assuming English
        substantive_english = [w for w in words if w not in COMMON_INDIAN_LOANWORDS and len(w) > 1]
        if len(substantive_english) >= 2 or len(words) >= 3:
            return "en-IN"
        return "en-IN"
    return None


UserTextCallback = Callable[[str, str], Awaitable[None]]


class LanguageRouter(FrameProcessor):
    """
    Keeps the LLM reply language and the TTS voice matched to the caller's language.
    Enforces a strict 2-3 check verification rule to prevent premature language changes.
    """

    def __init__(self, initial_language: str, on_user_text: Optional[UserTextCallback] = None,
                 hint_provider: Optional[Callable[[str], Optional[str]]] = None, **kwargs):
        if "loop" not in kwargs:
            try:
                kwargs["loop"] = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    kwargs["loop"] = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    kwargs["loop"] = loop
        super().__init__(**kwargs)
        self._current = initial_language if initial_language in VOICES else "te-IN"
        self._on_user_text = on_user_text
        self._hint_provider = hint_provider
        self._pending_lang: Optional[str] = None
        self._pending_count: int = 0

    @property
    def current_language(self) -> str:
        return self._current

    def prepare(self, text: str) -> tuple[str, Optional[TTSUpdateSettingsFrame]]:
        """
        Detect the language of a caller message. Returns the text annotated with the
        reply-language instruction and, when the language is properly verified, the frame
        that switches the TTS voice.
        """
        switch_frame = None
        clean_text = text.strip()

        # Step 1: Check for explicit caller instruction to change language (e.g. "Speak in English")
        explicit_request = detect_explicit_language_request(clean_text)
        if explicit_request and explicit_request in VOICES and explicit_request != self._current:
            logger.info(f"🗣 Explicit language switch requested by caller: {self._current} → {explicit_request}")
            self._pending_lang = None
            self._pending_count = 0
            self._current = explicit_request
            switch_frame = TTSUpdateSettingsFrame(
                delta=SarvamTTSService.Settings(voice=VOICES[explicit_request], language=explicit_request)
            )
        else:
            # Step 2: Continuous verification through multi-turn confirmation (2-3 check rule)
            detected = detect_language(clean_text)
            if detected:
                if detected == self._current:
                    # User spoke in current language: reset pending counter immediately
                    self._pending_lang = None
                    self._pending_count = 0
                elif detected in VOICES and self._should_switch(clean_text, detected):
                    logger.info(f"🗣 Verified language switch confirmed ({self._pending_count} checks): {self._current} → {detected} ({VOICES[detected]})")
                    self._pending_lang = None
                    self._pending_count = 0
                    self._current = detected
                    switch_frame = TTSUpdateSettingsFrame(
                        delta=SarvamTTSService.Settings(voice=VOICES[detected], language=detected)
                    )

        name = LANGUAGE_NAMES.get(self._current, "the customer's language")
        hint = self._hint_provider(clean_text) if self._hint_provider else None
        hint = f" {hint}" if hint else ""
        return f"{clean_text}\n(Reply only in {name}.{hint})", switch_frame

    def _should_switch(self, text: str, language: str) -> bool:
        """
        Carefully verify language candidate.
        Requires 3 consecutive turns in the new language (or 2 turns if substantive sentence >= 6 words)
        before switching, preventing accidental flips from loanwords or brief filler phrases.
        """
        words = [w.strip(",.?!").lower() for w in text.split() if any(ch.isalpha() for ch in w)]
        if len(words) < 2:
            # Single word or filler ("Hello", "హా", "Hmm", "Yes", "Ok") does not verify a language switch
            return False

        # Exclude utterances that are solely common loanwords in Indian business talk
        non_loanwords = [w for w in words if w not in COMMON_INDIAN_LOANWORDS]
        if not non_loanwords and language == "en-IN":
            logger.debug(f"Ignoring English loanword utterance without substantive content: {text}")
            return False

        # Increment verification counter for this candidate language
        if self._pending_lang == language:
            self._pending_count += 1
        else:
            self._pending_lang = language
            self._pending_count = 1

        # Check twice or thrice rule:
        # Check 1: never switch.
        # Check 2: switch only if the sentence is substantive and complete (>= 6 words).
        # Check 3: verified 3 consecutive turns in the new language -> switch.
        if self._pending_count >= 3:
            return True
        if self._pending_count >= 2 and len(words) >= 6:
            return True

        logger.info(f"🗣 Language candidate '{language}' detected (check {self._pending_count}/3) for caller speech: {text[:60]!r} — verifying before switching")
        return False

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
