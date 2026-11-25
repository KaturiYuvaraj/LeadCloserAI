"""
How the voice should say certain words: applied only to the text sent to the voice (Sarvam TTS). The
transcript, the CRM and the AI's own context keep the words as written.

25 Nov: the owner heard "whatsssssapp" and stretched words. The Telugu and Hindi voices read some English
words with an English hiss or drag; written the way Telugu or Hindi people say them, they sound natural.
Add a word here when a call shows one more.
"""

import re
from typing import Dict

SAY: Dict[str, Dict[str, str]] = {
    "te-IN": {
        "WhatsApp": "వాట్సాప్",
        "Whatsapp": "వాట్సాప్",
        "whatsapp": "వాట్సాప్",
    },
    "hi-IN": {
        "WhatsApp": "व्हाट्सऐप",
        "Whatsapp": "व्हाट्सऐप",
        "whatsapp": "व्हाट्सऐप",
    },
}


def _pattern(words):
    return re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
                      + r")(?![A-Za-z])")


_PATTERNS = {lang: _pattern(words) for lang, words in SAY.items()}


def for_voice(text: str, language: str) -> str:
    pattern = _PATTERNS.get(language)
    if not pattern or not text:
        return text
    return pattern.sub(lambda m: SAY[language][m.group(1)], text)
