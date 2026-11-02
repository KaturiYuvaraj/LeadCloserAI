"""
Automated Test Suite for English CRM Call Summaries.
Validates:
1. Telugu conversations produce 100% English executive CRM summaries and action items.
2. Hindi conversations produce 100% English executive CRM summaries and action items.
3. Fallback intelligence extraction produces clean English summaries.
4. SQLite database (leads and calls tables) contains zero Indic characters in summary fields.
5. Excel export generated matches the English header 'Call Summary (Executive Overview)'.
"""

import os
import sys
import re
import asyncio
from pathlib import Path

# Adjust path to find modules
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.stdout.reconfigure(encoding='utf-8')

from services.sales_agent import sales_agent
from database import get_connection, get_all_leads, save_call_record
from services.excel_service import generate_leads_export_excel
import openpyxl
import io

INDIC_REGEX = re.compile(r'[\u0900-\u0D7F]')


def test_db_has_zero_indic_in_summaries():
    """Verify that all records in SQLite database have English summaries, action items, and objections."""
    conn = get_connection()
    c = conn.cursor()

    leads = c.execute("SELECT id, name, last_call_summary, action_items, objections_noted FROM leads").fetchall()
    for row in leads:
        lead_id, name, summary, actions, objections = row[0], row[1], row[2], row[3], row[4]
        if summary:
            assert not INDIC_REGEX.search(summary), f"Lead #{lead_id} ({name}) summary has Indic characters: {summary}"
            assert "TechPulse" not in summary, f"Lead #{lead_id} mentions legacy TechPulse"
        if actions:
            assert not INDIC_REGEX.search(actions), f"Lead #{lead_id} action items have Indic characters: {actions}"
        if objections:
            assert not INDIC_REGEX.search(objections), f"Lead #{lead_id} objections have Indic characters: {objections}"

    calls = c.execute("SELECT id, summary, action_items, objections_raised, extracted_requirements FROM calls").fetchall()
    for row in calls:
        call_id, summary, actions, objections, reqs = row[0], row[1], row[2], row[3], row[4]
        if summary:
            assert not INDIC_REGEX.search(summary), f"Call #{call_id} summary has Indic characters: {summary}"
            assert "TechPulse" not in summary, f"Call #{call_id} mentions legacy TechPulse"
        if actions:
            assert not INDIC_REGEX.search(actions), f"Call #{call_id} action items have Indic characters: {actions}"
        if objections:
            assert not INDIC_REGEX.search(objections), f"Call #{call_id} objections have Indic characters: {objections}"
        if reqs:
            assert not INDIC_REGEX.search(reqs), f"Call #{call_id} requirements have Indic characters: {reqs}"

    conn.close()


def test_excel_export_english_headers_and_content():
    """Verify Excel export contains English headers and summaries."""
    leads = get_all_leads()
    excel_bytes = generate_leads_export_excel(leads)
    assert len(excel_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    assert "Call Summary (Executive Overview)" in headers
    summary_col_idx = headers.index("Call Summary (Executive Overview)") + 1

    for row_idx in range(2, ws.max_row + 1):
        cell_val = str(ws.cell(row=row_idx, column=summary_col_idx).value or "")
        if cell_val and cell_val != "No call yet":
            assert not INDIC_REGEX.search(cell_val), f"Row {row_idx} summary has non-English text: {cell_val}"
            assert "TechPulse" not in cell_val


async def test_telugu_conversation_intelligence_extraction():
    """Verify that a Telugu dialogue generates a concise English summary."""
    telugu_dialogue = [
        {"role": "assistant", "content": "నమస్కారం అండి! మేము S P Associates Software Company నుండి మాట్లాడుతున్నాము. మీ బిజినెస్ కోసం వెబ్‌సైట్ లేదా మొబైల్ యాప్ కావాలా అండి?"},
        {"role": "user", "content": "అవునండి, మా జ్యువెలరీ షాపు కోసం ఈ-కామర్స్ వెబ్‌సైట్ మరియు బిల్లింగ్ సాఫ్ట్‌వేర్ కావాలి. బడ్జెట్ ఎంత అవుతుంది?"},
        {"role": "assistant", "content": "చాలా మంచిదండి! ₹50,000 నుండి స్టార్ట్ అవుతుంది. రేపు ఉదయం 11 గంటలకు 10 నిమిషాల జూమ్ డెమో చూపిస్తాము, ఓకేనా అండి?"},
        {"role": "user", "content": "సరే, రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమో లింక్ వాట్సాప్‌లో పంపండి."}
    ]

    intel = await sales_agent.extract_call_intelligence(telugu_dialogue)
    summary = intel.get("summary", "")
    actions = intel.get("action_items", "")
    deal_stage = intel.get("deal_stage", "")

    assert summary, "Summary should not be empty"
    assert not INDIC_REGEX.search(summary), f"Summary contains Telugu/Indic script: {summary}"
    assert not INDIC_REGEX.search(actions), f"Action item contains Telugu/Indic script: {actions}"
    assert deal_stage in ["demo_scheduled", "qualified", "closed_won"]


async def test_hindi_conversation_intelligence_extraction():
    """Verify that a Hindi dialogue generates a concise English summary."""
    hindi_dialogue = [
        {"role": "assistant", "content": "नमस्ते सर! हम S P Associates Software Company से बात कर रहे हैं। आपके बिज़नेस के लिए कस्टम सॉफ़्टवेयर और मोबाइल ऐप के बारे में बात कर सकते हैं?"},
        {"role": "user", "content": "हाँ, हमारे ट्रांसपोर्ट बिज़नेस के लिए फ़्लीट ट्रैकिंग और ऑटोमेटेड बिलिंग सिस्टम चाहिए।"},
        {"role": "assistant", "content": "बिल्कुल सर! 3 से 4 हफ़्ते में तैयार हो जाएगा। क्या कल सुबह 11 बजे 10 मिनट का ऑनलाइन डेमो फ़िक्स करें?"},
        {"role": "user", "content": "ठीक है, कल सुबह 11:00 बजे का डेमो फ़िक्स कर दीजिए और व्हाट्सएप पर लिंक भेज दीजिए।"}
    ]

    intel = await sales_agent.extract_call_intelligence(hindi_dialogue)
    summary = intel.get("summary", "")
    actions = intel.get("action_items", "")
    deal_stage = intel.get("deal_stage", "")

    assert summary, "Summary should not be empty"
    assert not INDIC_REGEX.search(summary), f"Summary contains Hindi/Indic script: {summary}"
    assert not INDIC_REGEX.search(actions), f"Action item contains Hindi/Indic script: {actions}"
    assert deal_stage in ["demo_scheduled", "qualified", "closed_won"]


def test_empty_call_fallback_is_english():
    """Verify that empty or failed extraction returns clean English fallback."""
    import asyncio
    intel = asyncio.run(sales_agent.extract_call_intelligence([]))
    assert intel["summary"] == "No conversation took place on this call."
    assert not INDIC_REGEX.search(intel["action_items"])


if __name__ == "__main__":
    test_db_has_zero_indic_in_summaries()
    print("✓ test_db_has_zero_indic_in_summaries passed!")
    test_excel_export_english_headers_and_content()
    print("✓ test_excel_export_english_headers_and_content passed!")
    test_empty_call_fallback_is_english()
    print("✓ test_empty_call_fallback_is_english passed!")
    asyncio.run(test_telugu_conversation_intelligence_extraction())
    print("✓ test_telugu_conversation_intelligence_extraction passed!")
    asyncio.run(test_hindi_conversation_intelligence_extraction())
    print("✓ test_hindi_conversation_intelligence_extraction passed!")
    print("\nALL ENGLISH CALL SUMMARY TESTS PASSED SUCCESSFULLY! 🎯")
