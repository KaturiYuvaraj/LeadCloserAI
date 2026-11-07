"""
Multilingual Intelligence & Language Utilities.
Provides real-time language detection, TTS speaker routing, and localized greetings
for Telugu, Hindi, English, Tamil, Kannada, and Malayalam customer calling.
"""

from typing import Tuple, Optional, Dict, Any, Set
import re

# Common English technical, business, and conversational loanwords in Indian phone calls.
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

# Explicit language change request patterns
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

_EXPLICIT_REGEXES = {
    lang: [re.compile(p, re.IGNORECASE) for p in patterns]
    for lang, patterns in EXPLICIT_LANGUAGE_PATTERNS.items()
}


def detect_explicit_language_request(text: str) -> Optional[str]:
    """Detect if caller explicitly requested a language switch."""
    if not text:
        return None
    for lang, regex_list in _EXPLICIT_REGEXES.items():
        if any(r.search(text) for r in regex_list):
            return lang
    return None

# Romanized keyword hints for code-switching
HINDI_KEYWORDS = [
    "namaste", "namaskar", "aap", "hum", "hume", "chahiye", "kitna", "bataiye",
    "kya", "kab", "kaise", "theek", "shukriya", "bhai", "dukaan", "dost",
    "karo", "karenge", "baat", "haan", "nahi", "accha", "bilkul"
]
TELUGU_KEYWORDS = [
    "namaskaram", "andi", "cheppandi", "kavali", "entha", "ela", "meeku",
    "ledu", "avunu", "baagundi", "eppudu", "chustham", "vastundhi", "garu",
    "matladandi", "cheskondi", "chala", "manchi"
]
TAMIL_KEYWORDS = [
    "vanakkam", "enga", "romba", "nalla", "illai", "ama", "sollunga", "eppadi",
    "ungalukku", "thevai", "theriyum", "eppovum", "pesalam", "solreenga", "panlam"
]
KANNADA_KEYWORDS = [
    "namaskara", "beku", "illa", "hege", "nimge", "enu", "tumba", "heli",
    "yavaga", "kodi", "gottu", "matadana", "madona", "chennagide", "hogi"
]
MALAYALAM_KEYWORDS = [
    "namaskaram", "venam", "illa", "engane", "ningalkku", "entha", "valare",
    "parayu", "ariyaam", "undu", "aano", "samsarikkaam", "cheyyam", "nanni"
]


def detect_language(text: str) -> str:
    """
    Detect whether text is Telugu (te-IN), Hindi (hi-IN), English (en-IN),
    Tamil (ta-IN), Kannada (kn-IN), or Malayalam (ml-IN).
    Handles both native scripts and romanized code-switching.
    """
    if not text:
        return "te-IN"

    telugu_count = 0
    devanagari_count = 0
    tamil_count = 0
    kannada_count = 0
    malayalam_count = 0
    latin_count = 0

    for ch in text:
        code = ord(ch)
        if 0x0C00 <= code <= 0x0C7F:
            telugu_count += 1
        elif 0x0900 <= code <= 0x097F:
            devanagari_count += 1
        elif 0x0B80 <= code <= 0x0BFF:
            tamil_count += 1
        elif 0x0C80 <= code <= 0x0CFF:
            kannada_count += 1
        elif 0x0D00 <= code <= 0x0D7F:
            malayalam_count += 1
        elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
            latin_count += 1

    # Native script takes primary priority
    native_counts = {
        "te-IN": telugu_count,
        "hi-IN": devanagari_count,
        "ta-IN": tamil_count,
        "kn-IN": kannada_count,
        "ml-IN": malayalam_count,
    }
    best_lang, best_count = max(native_counts.items(), key=lambda item: item[1])
    if best_count > 0:
        return best_lang

    # If primarily latin script (English, Hinglish, Tenglish, Tanglish, Kanglish, Manglish)
    if latin_count > 0:
        lower = text.lower()
        scores = {
            "hi-IN": sum(1 for kw in HINDI_KEYWORDS if kw in lower),
            "te-IN": sum(1 for kw in TELUGU_KEYWORDS if kw in lower),
            "ta-IN": sum(1 for kw in TAMIL_KEYWORDS if kw in lower),
            "kn-IN": sum(1 for kw in KANNADA_KEYWORDS if kw in lower),
            "ml-IN": sum(1 for kw in MALAYALAM_KEYWORDS if kw in lower),
        }
        best_score_lang, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score > 0:
            return best_score_lang
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
    if speaker and speaker not in {"kavitha_te_conversation", "kavitha"}:
        return lang, speaker

    if lang == "hi-IN":
        chosen_speaker = "aditya_hi_sales" if model in {"bulbul:v4-flash", "bulbul:v4"} else "aditya"
        return "hi-IN", chosen_speaker

    elif lang == "en-IN":
        chosen_speaker = "simran_en_sales" if model in {"bulbul:v4-flash", "bulbul:v4"} else "simran"
        return "en-IN", chosen_speaker

    elif lang == "ta-IN":
        chosen_speaker = "meera_ta_conversation" if model in {"bulbul:v4-flash", "bulbul:v4"} else "meera"
        return "ta-IN", chosen_speaker

    elif lang == "kn-IN":
        chosen_speaker = "shreya_kn_conversation" if model in {"bulbul:v4-flash", "bulbul:v4"} else "shreya"
        return "kn-IN", chosen_speaker

    elif lang == "ml-IN":
        chosen_speaker = "arya_ml_conversation" if model in {"bulbul:v4-flash", "bulbul:v4"} else "arya"
        return "ml-IN", chosen_speaker

    else:
        # Default Telugu voice
        chosen_speaker = "kavitha_te_conversation" if model in {"bulbul:v4-flash", "bulbul:v4"} else "kavitha"
        return "te-IN", chosen_speaker


def get_localized_initial_greeting(
    agency_name: str,
    lead: Optional[Dict[str, Any]] = None,
    language_code: Optional[str] = None
) -> Tuple[str, str]:
    """
    Generate the opening hook greeting in the appropriate language
    (Telugu, Hindi, English, Tamil, Kannada, or Malayalam).
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

    elif lang == "ta-IN":
        if first_name:
            greeting = f"வணக்கம் {first_name}! நான் {agency_name}லிருந்து பேசுகிறேன். உங்கள் வணிகத்திற்கான {service} மென்பொருள் சேவைகள் பற்றி 2 நிமிடங்கள் பேசலாமா?"
        else:
            greeting = f"வணக்கம் சார்! நான் {agency_name}லிருந்து பேசுகிறேன். உங்கள் வணிகத்திற்கான தனிப்பயன் இணையதளம், மொபைல் ஆப் மற்றும் AI தீர்வுகள் பற்றி 2 நிமிடங்கள் பேசலாமா?"
        return greeting, "ta-IN"

    elif lang == "kn-IN":
        if first_name:
            greeting = f"ನಮಸ್ಕಾರ {first_name} ಅವರೇ! ನಾನು {agency_name} ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಿಮ್ಮ ವ್ಯವಹಾರಕ್ಕಾಗಿ {service} ಸಾಫ್ಟ್‌ವೇರ್ ಮತ್ತು AI ಸೇವೆಗಳ ಬಗ್ಗೆ 2 ನಿಮಿಷ ಮಾತನಾಡಬಹುದೇ?"
        else:
            greeting = f"ನಮಸ್ಕಾರ ಸರ್! ನಾನು {agency_name} ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಿಮ್ಮ ವ್ಯವಹಾರಕ್ಕಾಗಿ ಕಸ್ಟಮ್ ವೆಬ್‌ಸೈಟ್, ಮೊಬೈಲ್ ಆ್ಯಪ್ ಅಥವಾ AI ಪರಿಹಾರಗಳ ಕುರಿತು 2 ನಿಮಿಷ ಮಾತನಾಡಬಹುದೇ?"
        return greeting, "kn-IN"

    elif lang == "ml-IN":
        if first_name:
            greeting = f"നമസ്കാരം {first_name}! ഞാൻ {agency_name}-ൽ നിന്നാണ് സംസാരിക്കുന്നത്. നിങ്ങളുടെ ബിസിനസ്സിനായുള്ള {service} സോഫ്റ്റ്‌വെയർ ആവശ്യങ്ങളെക്കുറിച്ച് 2 മിനിറ്റ് സംസാരിക്കാമോ?"
        else:
            greeting = f"നമസ്കാരം സർ! ഞാൻ {agency_name}-ൽ നിന്നാണ് സംസാരിക്കുന്നത്. നിങ്ങളുടെ ബിസിനസ്സിനായുള്ള വെബ്സൈറ്റ്, മൊബൈൽ ആപ്പ് അല്ലെങ്കിൽ AI സൊല്യൂഷനുകളെക്കുറിച്ച് 2 മിനിറ്റ് സംസാരിക്കാമോ?"
        return greeting, "ml-IN"

    else:
        # Telugu (Default) - Natural spoken conversation style
        if first_name:
            greeting = f"నమస్కారం {first_name} గారు! నేను {agency_name} నుండి మాట్లాడుతున్నాను. మీ వ్యాపారం కోసం {service} సేవల గురించి ఒక్క నిమిషం మాట్లాడొచ్చా అండి?"
        else:
            greeting = f"నమస్కారం అండి! నేను {agency_name} నుండి మాట్లాడుతున్నాను. మీ వ్యాపారానికి వెబ్‌సైట్, మొబైల్ యాప్ లేదా సాఫ్ట్‌వేర్ సేవల గురించి ఒక్క నిమిషం మాట్లాడొచ్చా అండి?"
        return greeting, "te-IN"
