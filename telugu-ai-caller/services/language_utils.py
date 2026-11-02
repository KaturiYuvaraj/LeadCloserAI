"""
Multilingual Intelligence & Language Utilities.
Provides real-time language detection, TTS speaker routing, and localized greetings
for Telugu, Hindi, and English customer calling.
"""

from typing import Tuple, Optional, Dict, Any


def detect_language(text: str) -> str:
    """
    Detect whether text is Telugu (te-IN), Hindi (hi-IN), or English (en-IN).
    Handles both native scripts (Telugu Unicode, Devanagari) and romanized
    code-switching (Tenglish, Hinglish).
    """
    if not text:
        return "te-IN"

    telugu_count = 0
    devanagari_count = 0
    latin_count = 0

    for ch in text:
        code = ord(ch)
        if 0x0C00 <= code <= 0x0C7F:
            telugu_count += 1
        elif 0x0900 <= code <= 0x097F:
            devanagari_count += 1
        elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
            latin_count += 1

    # Native script takes primary priority
    if telugu_count > devanagari_count and telugu_count > 0:
        return "te-IN"
    if devanagari_count > telugu_count and devanagari_count > 0:
        return "hi-IN"

    # If primarily latin script (English, Hinglish, or Tenglish)
    if latin_count > 0:
        lower = text.lower()
        hindi_keywords = [
            "namaste", "namaskar", "aap", "hum", "hume", "chahiye", "kitna", "bataiye",
            "kya", "kab", "kaise", "theek", "shukriya", "bhai", "dukaan", "dost",
            "karo", "karenge", "baat", "haan", "nahi", "accha", "bilkul"
        ]
        telugu_keywords = [
            "namaskaram", "andi", "cheppandi", "kavali", "entha", "ela", "meeku",
            "ledu", "avunu", "baagundi", "eppudu", "chustham", "vastundhi", "garu",
            "matladandi", "cheskondi", "chala", "manchi"
        ]

        hi_score = sum(1 for kw in hindi_keywords if kw in lower)
        te_score = sum(1 for kw in telugu_keywords if kw in lower)

        if te_score > hi_score and te_score > 0:
            return "te-IN"
        elif hi_score > te_score and hi_score > 0:
            return "hi-IN"
        return "en-IN"

    return "te-IN"


def get_tts_speaker_and_lang(
    text: str,
    target_language_code: Optional[str] = None,
    speaker: Optional[str] = None,
    model: str = "bulbul:v4-flash"
) -> Tuple[str, str]:
    """
    Returns (target_language_code, speaker) for Sarvam TTS based on language.
    Guarantees valid speaker selection for the target language and model version.
    """
    lang = target_language_code or detect_language(text)

    # If user supplied a valid speaker that matches the language, preserve it
    if speaker and speaker != "kavitha_te_conversation":
        return lang, speaker

    if lang == "hi-IN":
        # Hindi voice
        if model in {"bulbul:v4-flash", "bulbul:v4"}:
            chosen_speaker = "aditya_hi_sales"
        elif model == "bulbul:v3":
            chosen_speaker = "aditya"
        else:
            chosen_speaker = "aditya"
        return "hi-IN", chosen_speaker

    elif lang == "en-IN":
        # English voice
        if model in {"bulbul:v4-flash", "bulbul:v4"}:
            chosen_speaker = "simran_en_sales"
        elif model == "bulbul:v3":
            chosen_speaker = "aditya"
        else:
            chosen_speaker = "simran"
        return "en-IN", chosen_speaker

    else:
        # Default Telugu voice
        if model in {"bulbul:v4-flash", "bulbul:v4"}:
            chosen_speaker = "kavitha_te_conversation"
        elif model == "bulbul:v3":
            chosen_speaker = "kavitha"
        else:
            chosen_speaker = "kavitha"
        return "te-IN", chosen_speaker


def get_localized_initial_greeting(
    agency_name: str,
    lead: Optional[Dict[str, Any]] = None,
    language_code: Optional[str] = None
) -> Tuple[str, str]:
    """
    Generate the opening hook greeting in the appropriate language (Telugu, Hindi, or English).
    Returns (greeting_text, language_code).
    """
    lead_name = lead.get("name") if lead else None
    first_name = lead_name.split()[0] if lead_name else None
    service = lead.get("service_needed", "సాఫ్ట్‌వేర్ & AI") if lead else "సాఫ్ట్‌వేర్ & AI"

    # Determine language preference from lead or parameter
    lang = language_code
    if not lang and lead:
        lang = lead.get("preferred_language")
        if not lang and lead.get("notes"):
            lang = detect_language(lead.get("notes", ""))

    if not lang:
        lang = "te-IN"  # default to primary regional language

    if lang == "hi-IN":
        if first_name:
            greeting = f"नमस्ते {first_name} जी! मैं {agency_name} से बात कर रहा हूँ। आपके बिज़नेस के लिए {service} सॉफ़्टवेयर और AI सेवाओं के बारे में 2 मिनट बात कर सकते हैं?"
        else:
            greeting = f"नमस्ते सर! मैं {agency_name} से बात कर रहा हूँ। क्या हम आपके बिज़नेस के लिए कस्टम वेबसाइट, मोबाइल ऐप या AI सॉफ़्टवेयर के बारे में 2 मिनट बात कर सकते हैं?"
        return greeting, "hi-IN"

    elif lang == "en-IN":
        if first_name:
            greeting = f"Hello {first_name}! I am calling from {agency_name}. May I have 2 quick minutes to discuss your requirement for {service}?"
        else:
            greeting = f"Hello! I am calling from {agency_name}. Could we take 2 quick minutes to discuss a custom website, mobile app, or AI solutions for your business?"
        return greeting, "en-IN"

    else:
        # Telugu (Default)
        if first_name:
            greeting = f"నమస్కారం {first_name} గారు! నేను {agency_name} నుండి మాట్లాడుతున్నాను. మీ వ్యాపారం కోసం {service} సేవల గురించి 2 నిమిషాలు మాట్లాడొచ్చా అండి?"
        else:
            greeting = f"నమస్కారం అండి! నేను {agency_name} నుండి మాట్లాడుతున్నాను. మీ వ్యాపారం కోసం కస్టమ్ వెబ్‌సైట్, మొబైల్ యాప్ లేదా AI సొల్యూషన్స్ గురించి 2 నిమిషాలు మాట్లాడొచ్చా అండి?"
        return greeting, "te-IN"

