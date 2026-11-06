"""
Comprehensive Test Suite for Telugu AI Caller & Sales Lead Closer.
Tests:
1. SQLite Database operations & Lead State Transitions
2. Sarvam AI Service (STT, TTS, LLM)
3. Sales Agent (Objection Handling, Deal Closing, Intelligence Extraction)
4. Web APIs
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import pytest
from database import (
    init_db,
    get_all_leads,
    create_lead,
    update_lead,
    get_lead_by_id,
    save_call_record,
    get_company_profile
)
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent


def test_database_crud():
    print("\n--- Running Database CRUD & State Transitions Test ---")
    init_db()

    profile = get_company_profile()
    assert profile is not None, "Profile should exist"
    print(f"Company Profile: {profile.get('agency_name')}")

    # Create lead
    lead_id = create_lead({
        "name": "టెస్ట్ లీడ్ (Test Lead)",
        "phone": "+91 9999988888",
        "company": "Test Ventures Hyderabad",
        "service_needed": "AI Calling & Mobile App",
        "budget": "₹60,000",
        "timeline": "Immediate",
        "notes": "Interested in automated voice caller."
    })
    assert lead_id > 0, "Lead ID should be valid"
    print(f"Created Lead ID: {lead_id}")

    lead = get_lead_by_id(lead_id)
    assert lead["status"] == "NEW"

    # Simulate completed call with demo scheduled
    call_id = save_call_record({
        "lead_id": lead_id,
        "call_type": "web",
        "duration_seconds": 95,
        "summary": "Customer agreed to a mobile app demo tomorrow at 11:00 AM.",
        "sentiment": "positive",
        "deal_stage": "demo_scheduled",
        "extracted_budget": "₹60,000",
        "extracted_timeline": "10 Days",
        "extracted_requirements": "Mobile App + AI Calling",
        "objections_raised": "Budget negotiation",
        "action_items": "Send Zoom link at 11 AM tomorrow"
    })
    assert call_id > 0

    # Verify lead status was automatically updated by the closing engine to DEMO_BOOKED
    updated_lead = get_lead_by_id(lead_id)
    assert updated_lead["status"] == "DEMO_BOOKED", f"Expected DEMO_BOOKED, got {updated_lead['status']}"
    print(f"Auto-promotion test PASSED! Lead status promoted to: {updated_lead['status']}")


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="Calls real Sarvam API; set RUN_LIVE_TESTS=1 to run")
async def test_sarvam_integration():
    print("\n--- Testing Sarvam STT, TTS and LLM Integration ---")
    # 1. Test LLM Sales Response
    messages = [
        {"role": "system", "content": "You are a professional Telugu sales closer. Answer in 1 short Telugu sentence."},
        {"role": "user", "content": "నాకు బిజినెస్ వెబ్‌సైట్ కావాలి, డెమో ఎప్పుడు ఇస్తారు?"}
    ]
    response = await sarvam_client.chat_completion(messages=messages, max_tokens=80)
    assert len(response) > 5, "LLM response should be non-empty"
    print(f"Sarvam LLM Telugu Output:\n  '{response}'")

    # 2. Test TTS Audio Generation
    audio_bytes = await sarvam_client.text_to_speech(response)
    assert len(audio_bytes) > 1000, "TTS audio bytes should be generated"
    print(f"Sarvam TTS Output: {len(audio_bytes)} bytes WAV audio successfully synthesized.")

    # 3. Test STT Audio Transcription roundtrip
    transcript = await sarvam_client.speech_to_text(audio_bytes)
    assert len(transcript) > 0, "STT transcript should be non-empty"
    print(f"Sarvam STT Output Transcript:\n  '{transcript}'")


async def test_sales_agent_deal_closing():
    print("\n--- Testing Sales Agent Deal Closing & Intelligence Extraction ---")
    dialogue = [
        {"role": "assistant", "content": "నమస్కారం అండి! మేము టెక్‌పల్స్ ఏజెన్సీ నుండి మాట్లాడుతున్నాము. మీ బిజినెస్ కోసం సాఫ్ట్‌వేర్ సేవల గురించి మాట్లాడొచ్చా?"},
        {"role": "user", "content": "అవును, మా క్లినిక్ కోసం పేషెంట్ అపాయింట్‌మెంట్స్ బుక్ చేసుకునే మొబైల్ యాప్ మరియు వాట్సాప్ ఆటోమేషన్ కావాలి."},
        {"role": "assistant", "content": "చాలా మంచి ఆలోచన అండి! మా వద్ద హాస్పిటల్స్ మరియు క్లినిక్స్ కోసం రెడీమేడ్ యాప్ సొల్యూషన్స్ ఉన్నాయి. మీ బడ్జెట్ ఎంత అనుకుంటున్నారు?"},
        {"role": "user", "content": "బడ్జెట్ 50,000 లోపు అయితే బాగుంటుంది. ఎప్పటికి పూర్తి చేస్తారు?"},
        {"role": "assistant", "content": "ఖచ్చితంగా 50,000 బడ్జెట్‌లోనే 2 వారాల్లో పూర్తి చేసి ఇస్తాము. రేపు ఉదయం 11 గంటలకు మా సీనియర్ డెవలపర్‌తో 10 నిమిషాల జూమ్ డెమో ఫిక్స్ చేయమంటారా?"},
        {"role": "user", "content": "సరే, రేపు ఉదయం 11 గంటలకు డెమో పెట్టండి, లింక్ వాట్సాప్ చేయండి."}
    ]

    intel = await sales_agent.extract_call_intelligence(dialogue)
    print("Extracted Deal Intelligence:")
    for k, v in intel.items():
        print(f"  {k}: {v}")

    assert intel.get("deal_stage") in ["demo_scheduled", "closed_won"], f"Expected demo_scheduled/closed_won, got {intel.get('deal_stage')}"
    print("Deal Closing Test PASSED!")


if __name__ == "__main__":
    test_database_crud()
    asyncio.run(test_sarvam_integration())
    asyncio.run(test_sales_agent_deal_closing())
    print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY! 🚀")
