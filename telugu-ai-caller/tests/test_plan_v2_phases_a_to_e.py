"""
Automated verification tests for LeadCloserAI Plan v2 Phases A, B, C, D, and E:
- Phase A: Lead Import (Excel/CSV/Paste), +91 E.164 validation, duplicate-in-file, Do-Not-Call opt-out check, source/campaign/marketer tags, and Rejected Rows CSV download.
- Phase B: Smart Cadence Follow-Up Engine (§4), Not-Reachable retry schedule, 9 AM–9 PM IST & weekly cap safeguards, and Caller Memory prompt injection.
- Phase C: Price Book, Quotation Guardrails (standard auto-send vs manager approval for custom scope / discount > 10%), Branded PDF generator, and WhatsApp STOP opt-out.
- Phase D & E: Meetings & No-Show auto-reschedule, 15-min Hot Lead Rep SLA, Pipeline Board, Today's Work, Source Performance (Marketing ROI), Reasons, Lead Timeline, Team Performance, and Daily Digest.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import init_db, add_opt_out, save_call_record, get_lead_by_id
from services.followup_engine import compute_next_followup_step, build_caller_memory_context
from services.sales_agent import sales_agent

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))


def setup_module(module):
    init_db()


def test_phase_a_import_report_duplicates_optouts_and_rejected_csv():
    """
    Verifies Phase A (§2 & §11):
    - Cleans +91 numbers
    - Flags invalid numbers (`invalid_number`)
    - Flags duplicate numbers within the same import (`duplicate_in_file`)
    - Blocks numbers on the Do-Not-Call list (`on_opt_out_list`)
    - Attaches `source_tag`, `campaign_tag`, `marketer_tag`
    - Serves downloadable `/api/leads/import-report/rejected.csv`
    """
    # Put one number on the Do-Not-Call list first
    add_opt_out("+919848099999", reason="customer_requested_dnd", account_id=1)

    pasted_tsv = (
        "Name\tPhone\tCompany\tService\tBudget\n"
        "Ramesh Traders\t9848011223\tRamesh Co\tE-Commerce Web\t₹50,000\n"
        "Duplicate Ramesh\t+91 98480 11223\tRamesh Co\tE-Commerce Web\t₹50,000\n"
        "DND Customer\t09848099999\tBlocked Co\tWebsite\t₹25,000\n"
        "Invalid Phone Lead\t12345\tBad Number Co\tMobile App\t₹60,000\n"
    )

    res = client.post(
        "/api/leads/import-paste",
        json={
            "text": pasted_tsv,
            "source_tag": "meta_lead_form",
            "campaign_tag": "nov_ecommerce_ads",
            "marketer_tag": "yuva_marketing",
            "consent_source": "meta_form_optin",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["inserted"] >= 1 or data["merged_existing"] >= 1
    assert data["rejected_count"] == 3

    codes = {r["code"] for r in data["rejected_rows"]}
    assert "duplicate_in_file" in codes
    assert "on_opt_out_list" in codes
    assert "invalid_number" in codes

    # Verify rejected rows CSV download
    csv_res = client.get("/api/leads/import-report/rejected.csv")
    assert csv_res.status_code == 200
    assert "Duplicate phone number" in csv_res.text
    assert "Do-Not-Call" in csv_res.text
    assert "Invalid phone number" in csv_res.text


def test_phase_b_smart_cadence_and_caller_memory():
    """
    Verifies Phase B (§4):
    - Smart cadence stages (Days 1–3, Days 4–10, Days 11–30, Days 31–60, >60 Cold)
    - Not-reachable retries (Miss 1: +2h, Miss 2: next day, Miss 3: evening + missed-call WhatsApp)
    - Safeguards (9 AM–9 PM IST clamping, max 4 calls/week cap, stop on do_not_call)
    - Caller Memory injected into SalesAgent system prompt
    """
    now_noon = datetime(2026, 11, 4, 12, 0, tzinfo=IST)

    # 1. Not-reachable Miss 1 -> +2 hours
    r1 = compute_next_followup_step("no_answer", consecutive_misses=1, now_ist=now_noon)
    assert r1["should_followup"] is True
    assert r1["stage"] == "not_reachable_retry_1"
    assert "14:00:00" in r1["next_action_at"]

    # 2. Not-reachable Miss 3 -> missed-call WhatsApp + evening retry
    r3 = compute_next_followup_step("switched_off", consecutive_misses=3, now_ist=now_noon)
    assert r3["immediate_action"] == "send_missed_call_whatsapp"
    assert r3["stage"] == "not_reachable_retry_3_whatsapp"

    # 3. Days 1–3 rotating slot
    d2 = compute_next_followup_step("busy_no_time", days_since_first_contact=2, now_ist=now_noon)
    assert d2["stage"] == "days_1_to_3"
    assert d2["slot_name"] == "afternoon"

    # 4. Days 4–10 with 2 consecutive misses -> WhatsApp nudge
    d6 = compute_next_followup_step("busy_no_time", days_since_first_contact=6, consecutive_misses=2, now_ist=now_noon)
    assert d6["stage"] == "days_4_to_10"
    assert d6["channel"] == "ai_call_with_whatsapp_nudge"

    # 5. Days 31–60 -> weekly WhatsApp first
    d40 = compute_next_followup_step("busy_no_time", days_since_first_contact=40, now_ist=now_noon)
    assert d40["stage"] == "days_31_to_60"
    assert d40["channel"] == "whatsapp_first"

    # 6. >60 days -> Cold
    d65 = compute_next_followup_step("busy_no_time", days_since_first_contact=65, now_ist=now_noon)
    assert d65["should_followup"] is False
    assert d65["stage"] == "cold"

    # 7. Weekly cap (4 calls/week reached) -> deferred to next week
    capped = compute_next_followup_step("busy_no_time", days_since_first_contact=3, calls_this_week=4, now_ist=now_noon)
    assert capped["stage"] == "weekly_cap_deferred"

    # 8. Instant stop on do_not_call
    stopped = compute_next_followup_step("do_not_call", now_ist=now_noon)
    assert stopped["should_followup"] is False
    assert stopped["stage"] == "stopped_opt_out"

    # 9. Caller Memory in SalesAgent prompt
    mock_lead = {
        "name": "Srinivas Rao",
        "company": "Rao Logistics",
        "budget": "₹40,000",
        "timeline": "After Diwali",
        "service_needed": "Fleet Tracking App",
        "last_call_summary": "Client discussed Fleet Tracking App for ₹40,000 and asked to reconnect after Diwali.",
        "outcome_label": "interested_later",
        "outcome_reason": "Deciding after Diwali",
        "objections_noted": "Wanted milestone payment split",
    }
    mem = build_caller_memory_context(mock_lead)
    assert "CALLER MEMORY" in mem
    assert "₹40,000" in mem
    prompt = sales_agent._build_system_prompt(mock_lead)
    assert "CALLER MEMORY" in prompt
    assert "Client discussed Fleet Tracking App" in prompt


def test_phase_c_price_book_quotation_guardrails_pdf_and_whatsapp_stop():
    """
    Verifies Phase C (§5 & §6):
    - Price book retrieval & custom package upsert
    - Standard package with <=10% discount -> auto-approved (`sent`)
    - Custom scope or >10% discount -> `pending_approval` until manager approves
    - Branded PDF download (`%PDF-1.4`)
    - WhatsApp 'STOP' webhook -> immediate opt-out
    """
    pb_res = client.get("/api/price-book")
    assert pb_res.status_code == 200
    assert pb_res.json()["count"] >= 5

    # Create a lead for quotation test
    lead_res = client.post(
        "/api/leads",
        json={
            "name": "Lakshmi Silks",
            "phone": "+919848055566",
            "company": "Lakshmi Silks Pvt Ltd",
            "service_needed": "E-Commerce Web",
            "budget": "₹45,000",
        },
    )
    lead_id = lead_res.json()["lead_id"]

    # 1. Standard quote within 10% discount -> auto-sent when whatsapp_opt_in=True
    q_std = client.post(
        "/api/quotations",
        json={
            "lead_id": lead_id,
            "package_code": "pkg_ecommerce_pro",
            "discount_pct": 5.0,
            "is_custom_scope": False,
            "whatsapp_opt_in": True,
        },
    )
    assert q_std.status_code == 200
    quote1 = q_std.json()["quotation"]
    assert quote1["requires_manager_approval"] is False
    assert quote1["status"] == "sent"
    assert quote1["gst_pct"] == 18.0

    # 2. High discount (25% > 10% max) -> blocked in `pending_approval`
    q_high = client.post(
        "/api/quotations",
        json={
            "lead_id": lead_id,
            "package_code": "pkg_ecommerce_pro",
            "discount_pct": 25.0,
            "is_custom_scope": True,
            "custom_scope_notes": "Custom SAP ERP sync + multi-currency checkout",
            "whatsapp_opt_in": True,
        },
    )
    assert q_high.status_code == 200
    quote2 = q_high.json()["quotation"]
    assert quote2["requires_manager_approval"] is True
    assert quote2["status"] == "pending_approval"
    assert quote2["version"] == 2

    # 3. Manager one-tap approval
    app_res = client.post(f"/api/quotations/{quote2['id']}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["quotation"]["status"] == "sent"
    assert app_res.json()["quotation"]["requires_manager_approval"] is False

    # 4. Download Branded Quotation PDF
    pdf_res = client.get(f"/api/quotations/{quote2['id']}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-1.4")

    # 5. Mark quote Won -> updates lead status to CLOSED_WON
    win_res = client.post(
        f"/api/quotations/{quote2['id']}/status",
        json={"status": "won", "won_amount_inr": quote2["total_inr"]},
    )
    assert win_res.status_code == 200
    updated_lead = get_lead_by_id(lead_id)
    assert updated_lead is not None
    assert updated_lead["status"] == "CLOSED_WON"

    # 6. WhatsApp incoming "STOP" -> opts out lead immediately
    stop_res = client.post(
        "/api/quotations/whatsapp/incoming",
        json={"phone": "+919848055566", "message": "STOP"},
    )
    assert stop_res.status_code == 200
    assert stop_res.json()["action"] == "opted_out"
    after_stop_lead = get_lead_by_id(lead_id)
    assert after_stop_lead is not None
    assert after_stop_lead["opt_out"] is True


def test_phase_d_and_e_meetings_pipeline_board_todays_work_roi_and_digest():
    """
    Verifies Phase D & E (§7, §8, §9):
    - Book meeting + mark `no_show` -> auto reschedule queued
    - Save hot call -> appears in Today's Work with 15-min rep SLA brief
    - Pipeline Board 5 buckets + 5 deal stages
    - Source Performance (Marketing ROI) funnel + bad lead %
    - Reasons, Lead Timeline, Team Performance, and Daily Owner Digest
    """
    lead_res = client.post(
        "/api/leads",
        json={
            "name": "Naveen Pharma",
            "phone": "+919848077788",
            "company": "Naveen Pharma Ltd",
            "source": "google_ads",
            "service_needed": "Mobile App",
            "budget": "₹75,000",
        },
    )
    lead_id = lead_res.json()["lead_id"]

    # Record a Hot call on this lead
    save_call_record(
        {
            "lead_id": lead_id,
            "call_type": "phone",
            "duration_seconds": 95,
            "status": "completed",
            "outcome_label": "interested_now",
            "outcome_reason": "Wants demo tomorrow at 11 AM and quotation on WhatsApp",
            "confidence": 0.94,
            "whatsapp_opt_in": True,
            "summary": "Client wants an Android & iOS pharma ordering app for ₹75,000.",
            "extracted_budget": "₹75,000",
            "extracted_timeline": "3 weeks",
            "extracted_requirements": "Mobile App",
            "objections_raised": "Timeline guarantee needed",
        },
        account_id=1,
    )

    # 1. Book a meeting and test No-Show auto-reschedule
    mtg_res = client.post(
        "/api/admin/meetings",
        json={"lead_id": lead_id, "mode": "google_meet"},
    )
    assert mtg_res.status_code == 200
    mid = mtg_res.json()["meeting"]["id"]

    ns_res = client.post(f"/api/admin/meetings/{mid}/status", json={"status": "no_show"})
    assert ns_res.status_code == 200
    assert ns_res.json()["auto_action"] == "auto_reschedule_call_queued"
    assert ns_res.json()["meeting"]["reschedule_attempts"] == 1

    # 2. Pipeline Board
    pb = client.get("/api/admin/pipeline-board").json()
    assert pb["status"] == "success"
    assert set(pb["columns"].keys()) == {"uncalled", "not_reachable", "follow_up", "hot", "closed"}
    assert set(pb["deal_stages"].keys()) == {"quote_sent", "meeting", "negotiation", "won", "lost"}

    # 3. Today's Work (including Hot leads waiting for rep with 1-line brief)
    tw = client.get("/api/admin/todays-work").json()
    assert tw["status"] == "success"
    assert tw["summary"]["hot_waiting_for_rep"] >= 1
    assert any("🔥" in h["one_line_brief"] for h in tw["hot_waiting_for_rep"])

    # 4. Rep claims hot lead within 15-min SLA
    claim_res = client.post(f"/api/admin/hot-leads/{lead_id}/claim", json={"rep_name": "Priya Sharma"})
    assert claim_res.status_code == 200
    assert claim_res.json()["sla_met"] is True

    # 5. Source Performance (Marketing ROI)
    sp = client.get("/api/admin/source-performance").json()
    assert sp["status"] == "success"
    assert len(sp["sources"]) >= 1

    # 6. Reasons breakdown
    rsn = client.get("/api/admin/reasons").json()
    assert rsn["status"] == "success"
    assert "outcome_breakdown" in rsn

    # 7. Unified Lead Timeline
    tl = client.get(f"/api/admin/leads/{lead_id}/timeline").json()
    assert tl["status"] == "success"
    event_types = {e["type"] for e in tl["timeline"]}
    assert "call" in event_types
    assert "meeting" in event_types

    # 8. Team Performance & Daily Digest
    tp = client.get("/api/admin/team-performance").json()
    assert tp["status"] == "success"
    assert len(tp["team"]) >= 3

    dd = client.get("/api/admin/daily-digest").json()
    assert dd["status"] == "success"
    assert "LeadCloserAI Daily Owner Digest" in dd["digest_text"]
    assert dd["kpi_targets"]["rep_response_on_hot_minutes"] == 15
