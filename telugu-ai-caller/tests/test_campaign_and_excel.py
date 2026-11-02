"""
Test Suite for Excel / CSV Ingestion and Autonomous Auto-Calling Campaign.
"""

import sys
import os
import io
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from services.excel_service import parse_excel_or_csv, generate_sample_excel_template
from services.campaign_service import campaign_service
from database import (
    init_db,
    batch_create_leads,
    get_all_leads,
    get_lead_by_id,
    get_call_history
)


def test_excel_generation_and_parsing():
    print("\n--- Testing Excel Template Generation & Ingestion ---")
    init_db()

    # 1. Generate sample template
    template_bytes = generate_sample_excel_template()
    assert len(template_bytes) > 1000, "Template should be a valid Excel binary"
    print(f"Generated Excel template: {len(template_bytes)} bytes.")

    # 2. Parse the generated template
    leads, errors = parse_excel_or_csv(template_bytes, "leads_template.xlsx")
    assert len(leads) >= 3, f"Expected at least 3 leads, parsed {len(leads)}"
    assert len(errors) == 0, f"Expected 0 errors, got: {errors}"
    print(f"Successfully parsed {len(leads)} leads from Excel:")
    for l in leads:
        print(f"  - {l['name']} | Phone: {l['phone']} | Service: {l['service_needed']} | Budget: {l['budget']}")

    # 3. Batch insert into database
    inserted, updated = batch_create_leads(leads)
    print(f"Database batch ingest result: {inserted} inserted, {updated} updated.")
    assert inserted + updated == len(leads)

    # 4. Test CSV parsing as well
    csv_data = """Customer Name,Phone Number,Company Name,Service Needed,Estimated Budget,Timeline,Notes
వెంకట్ రాజు (Venkat Raju),+91 9123456789,Raju Electronics,AI Chatbot & E-Commerce,₹45000,Immediate,Customer needs WhatsApp bot for orders
శివ కుమార్ (Shiva Kumar),+91 9345678901,Shiva Logistics,Mobile App,₹80000,1 Month,Delivery tracking app
""".encode("utf-8")

    csv_leads, csv_errors = parse_excel_or_csv(csv_data, "leads.csv")
    assert len(csv_leads) == 2, f"Expected 2 leads from CSV, got {len(csv_leads)}"
    print(f"CSV Parse PASSED! Parsed {len(csv_leads)} leads from CSV.")

    ins, upd = batch_create_leads(csv_leads)
    print(f"CSV Ingestion into DB: {ins} inserted, {upd} updated.")


async def test_autonomous_calling_campaign():
    print("\n--- Testing Autonomous Auto-Calling Campaign ---")
    init_db()

    # Get two leads to call
    all_leads = get_all_leads()
    test_leads = all_leads[:2]
    lead_ids = [l["id"] for l in test_leads]

    print(f"Starting Campaign on Lead IDs: {lead_ids}")
    started = await campaign_service.start_campaign(
        lead_ids=lead_ids,
        mode="simulation",
        delay_seconds=1
    )
    assert started is True, "Campaign should start successfully"

    # Monitor status until finished
    for _ in range(40):
        await asyncio.sleep(1)
        status = campaign_service.get_status()
        print(f"Campaign Progress: {status['completed_leads']}/{status['total_leads']} ({status['progress_percent']}%) | Demos: {status['results']['demo_scheduled']}")
        if not status["is_running"]:
            break

    final_status = campaign_service.get_status()
    assert final_status["completed_leads"] == 2, f"Expected 2 completed leads, got {final_status['completed_leads']}"
    assert final_status["results"]["demo_scheduled"] + final_status["results"]["closed_won"] > 0

    # Verify calls saved in database
    calls = get_call_history(limit=5)
    assert len(calls) >= 2
    print(f"Recent Call Record: {calls[0]['summary']} | Deal Stage: {calls[0]['deal_stage']}")

    print("\nAUTONOMOUS AUTO-CALLING CAMPAIGN TEST PASSED! 🚀")


if __name__ == "__main__":
    test_excel_generation_and_parsing()
    asyncio.run(test_autonomous_calling_campaign())
    print("\nALL EXCEL & CAMPAIGN TESTS PASSED SUCCESSFULLY! 🎯")

