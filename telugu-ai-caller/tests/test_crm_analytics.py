"""
Test Suite for Modules 8 & 11: CRM Pipeline Interactions and Executive Analytics Reporting.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import (
    create_lead,
    get_lead_by_id,
    update_lead,
    save_call_record,
    get_analytics_summary
)


class CrmAndAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_analytics_summary_database(self):
        """
        Verify database calculation for executive analytics KPIs.
        """
        summary = get_analytics_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("total_leads", summary)
        self.assertIn("total_calls", summary)
        self.assertIn("conversion_rate", summary)
        self.assertIn("demos_booked", summary)
        self.assertIn("closed_won", summary)
        self.assertIn("cpql_inr", summary)
        self.assertIn("objections", summary)
        self.assertIn("languages", summary)
        self.assertIn("employees", summary)
        self.assertGreaterEqual(summary["total_leads"], 0)
        self.assertGreaterEqual(summary["conversion_rate"], 0.0)
        self.assertGreaterEqual(len(summary["employees"]), 1)

    def test_get_analytics_overview_endpoint(self):
        """
        Verify GET /api/analytics/overview returns HTTP 200 and structured data.
        """
        resp = self.client.get("/api/analytics/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("total_leads", data["data"])
        self.assertIn("status_counts", data["data"])

    def test_lead_stage_transitions(self):
        """
        Verify pipeline lead lifecycle from NEW -> QUALIFIED -> DEMO_BOOKED -> CLOSED_WON.
        """
        lead_id = create_lead({
            "name": "Subba Rao",
            "phone": "+91 94401 22334",
            "company": "Subba Rao Logistics",
            "service_needed": "Fleet Management App",
            "status": "NEW"
        })

        lead = get_lead_by_id(lead_id)
        self.assertEqual(lead["status"], "NEW")

        # 1. Qualify lead
        ok = update_lead(lead_id, {"status": "QUALIFIED", "last_call_stage": "qualified"})
        self.assertTrue(ok)
        lead = get_lead_by_id(lead_id)
        self.assertEqual(lead["status"], "QUALIFIED")

        # 2. Book demo
        ok = update_lead(lead_id, {"status": "DEMO_BOOKED", "last_call_stage": "demo_booked"})
        self.assertTrue(ok)
        lead = get_lead_by_id(lead_id)
        self.assertEqual(lead["status"], "DEMO_BOOKED")

        # 3. Close deal
        ok = update_lead(lead_id, {"status": "CLOSED_WON", "last_call_stage": "closed_won"})
        self.assertTrue(ok)
        lead = get_lead_by_id(lead_id)
        self.assertEqual(lead["status"], "CLOSED_WON")

    def test_objection_categorization_in_analytics(self):
        """
        Verify objections raised during calls are categorized into Pricing, Existing, WhatsApp, or Custom.
        """
        lead_id = create_lead({
            "name": "Harish Patel",
            "phone": "+91 98250 88776",
            "company": "Patel Textiles"
        })

        # Record a call with pricing objection
        save_call_record({
            "lead_id": lead_id,
            "call_type": "web",
            "phone_number": "+91 98250 88776",
            "duration_seconds": 95,
            "status": "completed",
            "summary": "Discussed textile billing software, client requested discount.",
            "sentiment": "hesitant",
            "deal_stage": "qualifying",
            "objections_raised": "Client feels the initial price and budget is a bit expensive"
        })

        summary = get_analytics_summary()
        self.assertIn("objections", summary)
        self.assertGreater(summary["objections"]["pricing"], 0)


if __name__ == "__main__":
    unittest.main()
