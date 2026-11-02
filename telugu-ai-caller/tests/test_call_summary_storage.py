"""
Test Suite for Call Summary Storage, Persistence, and Excel Export.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from database import (
    init_db,
    create_lead,
    get_lead_by_id,
    save_call_record,
    get_call_by_id,
    get_calls_for_lead,
    get_all_leads
)
from services.excel_service import generate_leads_export_excel


def test_call_summary_storage_and_export():
    print("\n--- Testing Call Summary Storage & Persistence in Database ---")
    init_db()

    # 1. Create a lead
    lead_id = create_lead({
        "name": "నాగరాజు (Nagaraju)",
        "phone": "+91 9888877777",
        "company": "Nagaraju Hardware & Paints",
        "service_needed": "Custom Billing Software & WhatsApp Bot",
        "budget": "₹45,000",
        "timeline": "Immediate",
        "notes": "Looking for offline-capable billing POS"
    })
    assert lead_id > 0
    print(f"Created Lead ID: {lead_id}")

    lead_before = get_lead_by_id(lead_id)
    assert lead_before["last_call_summary"] is None

    # 2. Simulate AI Call with detailed summary of what was talked in the call
    simulated_summary = (
        "కస్టమర్ నాగరాజు గారితో బిల్లింగ్ సాఫ్ట్‌వేర్ మరియు వాట్సాప్ ఇన్వాయిసింగ్ సేవల గురించి మాట్లాడాము. "
        "కస్టమర్ ₹40,000 బడ్జెట్‌లో ఆఫ్‌లైన్ బిల్లింగ్ ఫీచర్ కావాలని కోరారు. "
        "రేపు ఉదయం 11:30 గంటలకు 10 నిమిషాల జూమ్ డెమోకు అంగీకరించారు."
    )
    simulated_objections = "ధర తగ్గించాలి మరియు ఇంటర్నెట్ లేకపోయినా బిల్లింగ్ సాగాలి."
    simulated_action = "రేపు ఉదయం 11:30 గంటలకు జూమ్ మీటింగ్ లింక్ మరియు ప్రైసింగ్ కొటేషన్ వాట్సాప్ ద్వారా పంపాలి."

    call_id = save_call_record({
        "lead_id": lead_id,
        "call_type": "web",
        "phone_number": "+91 9888877777",
        "duration_seconds": 115,
        "status": "completed",
        "summary": simulated_summary,
        "sentiment": "positive",
        "deal_stage": "demo_scheduled",
        "extracted_budget": "₹40,000",
        "extracted_timeline": "1 Week",
        "extracted_requirements": "Offline Billing POS + WhatsApp Bot",
        "objections_raised": simulated_objections,
        "action_items": simulated_action,
        "transcript": '[{"role": "assistant", "content": "నమస్కారం నాగరాజు గారు!"}, {"role": "user", "content": "మాకు బిల్లింగ్ సాఫ్ట్‌వేర్ డెమో కావాలి."}]'
    })
    assert call_id > 0
    print(f"Call recorded with ID: {call_id}")

    # 3. Verify that the lead record in SQLite now has the full call summary stored!
    lead_after = get_lead_by_id(lead_id)
    assert lead_after["last_call_summary"] == simulated_summary, "Lead should have last_call_summary persisted"
    assert lead_after["last_call_stage"] == "demo_scheduled"
    assert lead_after["last_call_sentiment"] == "positive"
    assert lead_after["objections_noted"] == simulated_objections
    assert lead_after["action_items"] == simulated_action
    assert lead_after["last_called_at"] is not None
    assert lead_after["status"] == "DEMO_BOOKED"

    print("Lead record successfully updated with Call Summary:")
    print(f"  - Summary: {lead_after['last_call_summary'][:90]}...")
    print(f"  - Stage: {lead_after['last_call_stage']}")
    print(f"  - Action Item: {lead_after['action_items']}")
    print(f"  - Called At: {lead_after['last_called_at']}")

    # 4. Verify get_call_by_id and get_calls_for_lead
    call_record = get_call_by_id(call_id)
    assert call_record is not None
    assert call_record["summary"] == simulated_summary
    assert call_record["lead_name"] == "నాగరాజు (Nagaraju)"
    print("Call record retrieval by ID verified!")

    lead_calls = get_calls_for_lead(lead_id)
    assert len(lead_calls) >= 1
    print(f"Lead call history verified ({len(lead_calls)} calls found for this lead).")

    # 5. Verify Excel Export with Call Summary column
    all_leads = get_all_leads()
    export_bytes = generate_leads_export_excel(all_leads)
    assert len(export_bytes) > 2000, "Exported Excel binary should be non-empty"
    print(f"Generated leads export Excel with summaries: {len(export_bytes)} bytes.")

    print("\nALL CALL SUMMARY STORAGE AND EXPORT TESTS PASSED! 🚀")


if __name__ == "__main__":
    test_call_summary_storage_and_export()

