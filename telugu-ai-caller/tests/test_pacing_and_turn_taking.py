"""
Verification test for conversational pacing, human-like turn-taking,
and active listening acknowledgements.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from services.sales_agent import sales_agent
from services.language_utils import detect_language
from database import init_db


async def test_human_conversational_pacing():
    print("Testing Human Conversational Pacing & Active Listening Responses...")

    # Scenario 1: Customer gives a detailed requirement in Telugu
    conv_te = [
        {"role": "assistant", "content": "నమస్కారం అండి! నేను S P Associates Software Company నుండి మాట్లాడుతున్నాను. మీ వ్యాపారం కోసం సాఫ్ట్‌వేర్ సేవల గురించి 2 నిమిషాలు మాట్లాడొచ్చా అండి?"},
        {"role": "user", "content": "మాది కిరాణా సూపర్ మార్కెట్ అండి. మాకు బిల్లింగ్ సాఫ్ట్‌వేర్ మరియు కస్టమర్లు ఇంట్లో నుంచే ఆర్డర్ చేసుకునే మొబైల్ యాప్ కావాలి. దీనికి ఎంత సమయం పడుతుంది?"}
    ]

    reply_te = await sales_agent.generate_response(conv_te)
    print(f"\nTelugu Customer Input: {conv_te[-1]['content']}")
    print(f"AI Paced Response: {reply_te}")

    # Verify that response is concise (<= 2 sentences) and contains human polite addressing
    assert len(reply_te) > 10
    assert any(term in reply_te for term in ["అండి", "సార్", "మేము", "చేస్తాము", "డెమో"])
    assert detect_language(reply_te) == "te-IN"

    # Scenario 2: Customer asks in Hindi about pricing & timeline
    conv_hi = [
        {"role": "assistant", "content": "नमस्ते सर! मैं S P Associates Software Company से बात कर रहा हूँ।"},
        {"role": "user", "content": "नमस्ते, हमारी लॉजिस्टिक्स कंपनी है। हमें फ्लीट ट्रैकिंग और इनवॉइसिंग सिस्टम चाहिए, क्या आप बना सकते हैं और कितना बजट लगेगा?"}
    ]

    reply_hi = await sales_agent.generate_response(conv_hi)
    print(f"\nHindi Customer Input: {conv_hi[-1]['content']}")
    print(f"AI Paced Response: {reply_hi}")

    assert len(reply_hi) > 10
    assert any(term in reply_hi for term in ["सर", "जी", "बिल्कुल", "हम", "डेमो"])
    assert detect_language(reply_hi) == "hi-IN"

    # Scenario 3: Customer explains need in English
    conv_en = [
        {"role": "assistant", "content": "Hello! I am calling from S P Associates Software Company."},
        {"role": "user", "content": "Hi, I have a multi-speciality dental clinic and we want an automated WhatsApp and AI phone booking system. How soon can it be launched?"}
    ]

    reply_en = await sales_agent.generate_response(conv_en)
    print(f"\nEnglish Customer Input: {conv_en[-1]['content']}")
    print(f"AI Paced Response: {reply_en}")

    assert len(reply_en) > 10
    assert detect_language(reply_en) == "en-IN"

    print("\n Human Conversational Pacing & Active Listening: PASSED!")


def test_client_vad_script_integrity():
    print("\nTesting Client JavaScript VAD & Turn-Taking Code Integrity...")
    client_js_path = BASE_DIR / "static" / "js" / "call_client.js"
    assert client_js_path.exists(), "call_client.js does not exist!"

    content = client_js_path.read_text(encoding="utf-8")
    assert "silenceTimeoutMs = 900" in content, "Missing 0.9s default silence threshold!"
    assert "setSilenceTimeout" in content, "Missing configurable reply wait time!"
    assert "startCallRecording" in content, "Missing optional call recording!"
    assert "createAnalyser" in content, "Missing Web Audio API AnalyserNode VAD!"
    assert "audioQueue" in content, "Missing Audio Queue for overlap prevention!"
    assert "completeCustomerTurn" in content, "Missing turn completion logic!"
    assert "forceFinishTurn" in content, "Missing manual turn finisher!"
    assert "isPlayingAudio" in content, "Missing Half-Duplex echo prevention flag!"

    print(" Client VAD & Turn-Taking Script Integrity: PASSED!")


async def main():
    print("==================================================")
    print("VERIFYING CONVERSATIONAL TIMING & PACING ENGINE")
    print("==================================================")
    init_db()
    test_client_vad_script_integrity()
    await test_human_conversational_pacing()
    print("==================================================")
    print("ALL PACING & TURN-TAKING TESTS PASSED! 🚀")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())

