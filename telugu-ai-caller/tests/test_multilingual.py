"""
Multilingual AI Calling Engine Verification Test.
Tests Telugu, Hindi, and English language detection, LLM dialogue mirroring,
TTS voice generation, and Excel ingestion.
"""

import sys
import os
import asyncio
import pytest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Force UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from services.language_utils import detect_language, get_tts_speaker_and_lang, get_localized_initial_greeting
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from services.excel_service import parse_excel_or_csv, generate_sample_excel_template
from database import init_db, create_lead, get_lead_by_id, get_company_profile


def test_language_detection():
    print("Testing Language Detection...")
    assert detect_language("నమస్కారం అండి! మేము సాఫ్ట్‌వేర్ సేవల గురించి మాట్లాడుతున్నాము.") == "te-IN"
    assert detect_language("नमस्ते सर! हमें हमारी दुकान के लिए बिलिंग सॉफ़्टवेयर चाहिए।") == "hi-IN"
    assert detect_language("Hello! We need an e-commerce website with payment gateway.") == "en-IN"
    assert detect_language("enti andi entha budget avtundi app ki?") == "te-IN"
    assert detect_language("namaste bhai hume billing app chahiye kitna lagega?") == "hi-IN"
    assert detect_language("வணக்கம் சார், உங்கள் மென்பொருள் சேவைக்கு நன்றி.") == "ta-IN"
    assert detect_language("ನಮಸ್ಕಾರ, ನಮಗೆ ವೆಬ್‌ಸೈಟ್ ಮತ್ತು ಆ್ಯಪ್ ಬೇಕು.") == "kn-IN"
    assert detect_language("നമസ്കാരം, ഞങ്ങൾക്ക് പുതിയ സോഫ്റ്റ്‌വെയർ വേണം.") == "ml-IN"
    print(" Language Detection: PASSED")


def test_localized_greetings():
    print("Testing Localized Initial Greetings...")
    agency = "S P Associates Software Company"
    g_te, lang_te = get_localized_initial_greeting(agency, lead={"name": "రమేష్"}, language_code="te-IN")
    assert "S P Associates Software Company" in g_te
    assert "నమస్కారం" in g_te
    assert lang_te == "te-IN"

    g_hi, lang_hi = get_localized_initial_greeting(agency, lead={"name": "अमित"}, language_code="hi-IN")
    assert "S P Associates Software Company" in g_hi
    assert "नमस्ते" in g_hi
    assert lang_hi == "hi-IN"

    g_en, lang_en = get_localized_initial_greeting(agency, lead={"name": "John"}, language_code="en-IN")
    assert "S P Associates Software Company" in g_en
    assert "Hello" in g_en
    assert lang_en == "en-IN"

    g_ta, lang_ta = get_localized_initial_greeting(agency, lead={"name": "முருகன்"}, language_code="ta-IN")
    assert "S P Associates Software Company" in g_ta
    assert "வணக்கம்" in g_ta
    assert lang_ta == "ta-IN"

    g_kn, lang_kn = get_localized_initial_greeting(agency, lead={"name": "ಸುರೇಶ್"}, language_code="kn-IN")
    assert "S P Associates Software Company" in g_kn
    assert "ನಮಸ್ಕಾರ" in g_kn
    assert lang_kn == "kn-IN"

    g_ml, lang_ml = get_localized_initial_greeting(agency, lead={"name": "മനോജ്"}, language_code="ml-IN")
    assert "S P Associates Software Company" in g_ml
    assert "നമസ്കാരം" in g_ml
    assert lang_ml == "ml-IN"
    print(" Localized Initial Greetings: PASSED")


def test_tts_speaker_routing():
    print("Testing TTS Speaker & Language Code Routing...")
    lang_te, spk_te = get_tts_speaker_and_lang("నమస్కారం అండి")
    assert lang_te == "te-IN"
    assert "kavitha" in spk_te

    lang_hi, spk_hi = get_tts_speaker_and_lang("नमस्ते सर, आपका स्वागत है")
    assert lang_hi == "hi-IN"
    assert "aditya" in spk_hi

    lang_en, spk_en = get_tts_speaker_and_lang("Hello sir, we are ready to build your app")
    assert lang_en == "en-IN"
    assert "simran" in spk_en or "aditya" in spk_en

    lang_ta, spk_ta = get_tts_speaker_and_lang("வணக்கம் சார்")
    assert lang_ta == "ta-IN"

    lang_kn, spk_kn = get_tts_speaker_and_lang("ನಮಸ್ಕಾರ ಸರ್")
    assert lang_kn == "kn-IN"

    lang_ml, spk_ml = get_tts_speaker_and_lang("നമസ്കാരം സാർ")
    assert lang_ml == "ml-IN"
    print(" TTS Speaker Routing: PASSED")


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="Calls real Sarvam API; set RUN_LIVE_TESTS=1 to run")
async def test_trilingual_llm_conversations():
    print("Testing Trilingual LLM Dialogue & Voice Synthesis...")

    # 1. Telugu Turn
    te_history = [
        {"role": "assistant", "content": "నమస్కారం అండి! నేను S P Associates Software Company నుండి మాట్లాడుతున్నాను."},
        {"role": "user", "content": "మాకు ఒక రిటైల్ షాప్ ఉంది, బిల్లింగ్ మరియు కస్టమర్ ఆర్డరింగ్ యాప్ కావాలి, ఎంత సమయం పడుతుంది?"}
    ]
    te_reply = await sales_agent.generate_response(te_history)
    print(f"Telugu AI reply: {te_reply}")
    assert len(te_reply) > 10
    assert detect_language(te_reply) == "te-IN"
    te_audio = await sarvam_client.text_to_speech(te_reply)
    assert len(te_audio) > 1000

    # 2. Hindi Turn
    hi_history = [
        {"role": "assistant", "content": "नमस्ते सर! मैं S P Associates Software Company से बात कर रहा हूँ।"},
        {"role": "user", "content": "नमस्ते, हमारी लॉजिस्टिक्स कंपनी के लिए वेब पोर्टल और ट्रैकिंग ऐप बनवाना है, क्या आप डेमो दे सकते हैं?"}
    ]
    hi_reply = await sales_agent.generate_response(hi_history)
    print(f"Hindi AI reply: {hi_reply}")
    assert len(hi_reply) > 10
    assert detect_language(hi_reply) == "hi-IN"
    hi_audio = await sarvam_client.text_to_speech(hi_reply)
    assert len(hi_audio) > 1000

    # 3. English Turn
    en_history = [
        {"role": "assistant", "content": "Hello! I am calling from S P Associates Software Company."},
        {"role": "user", "content": "Hi, we are looking for an AI voice caller and customer support chatbot for our clinic. How does it work?"}
    ]
    en_reply = await sales_agent.generate_response(en_history)
    print(f"English AI reply: {en_reply}")
    assert len(en_reply) > 10
    assert detect_language(en_reply) == "en-IN"
    en_audio = await sarvam_client.text_to_speech(en_reply)
    assert len(en_audio) > 1000

    print(" Trilingual LLM & Voice Generation: PASSED")


def test_excel_multilingual_template_and_parsing():
    print("Testing Excel Template & Language Ingestion...")
    template_bytes = generate_sample_excel_template()
    assert len(template_bytes) > 2000

    # Parse template back
    leads, errors = parse_excel_or_csv(template_bytes, "template.xlsx")
    assert len(leads) >= 3
    assert not errors

    languages = [l.get("preferred_language") for l in leads]
    assert "te-IN" in languages
    assert "hi-IN" in languages
    assert "en-IN" in languages
    print(f" Parsed leads with languages: {languages}")
    print(" Excel Multilingual Ingestion: PASSED")


async def main():
    print("==================================================")
    print("STARTING MULTILINGUAL AI CALLER VERIFICATION SUITE")
    print("==================================================")
    init_db()
    test_language_detection()
    test_localized_greetings()
    test_tts_speaker_routing()
    test_excel_multilingual_template_and_parsing()
    await test_trilingual_llm_conversations()
    print("==================================================")
    print("ALL MULTILINGUAL TESTS PASSED WITH 100% SUCCESS! ")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())

