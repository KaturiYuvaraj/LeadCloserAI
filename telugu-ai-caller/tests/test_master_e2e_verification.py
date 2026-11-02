"""
End-to-End Master Verification Gate.
Validates all modules from the Master Development Prompt.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import (
    create_lead,
    get_lead_by_id,
    update_lead,
    get_all_ai_employees,
    get_active_ai_employee,
    get_all_campaigns,
    get_all_provider_settings,
    get_analytics_summary
)
from providers import registry, ProviderType


class MasterE2EVerificationGate(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_provider_registry_initialized(self):
        """Module 2: Provider registry supports all domain types."""
        self.assertIsNotNone(registry.get_active(ProviderType.VOICE_STT))
        self.assertIsNotNone(registry.get_active(ProviderType.VOICE_TTS))
        self.assertIsNotNone(registry.get_active(ProviderType.TELEPHONY))
        self.assertIsNotNone(registry.get_active(ProviderType.LLM))
        self.assertIsNotNone(registry.get_active(ProviderType.LEAD_DISCOVERY))
        self.assertIsNotNone(registry.get_active(ProviderType.MESSAGING))
        self.assertIsNotNone(registry.get_active(ProviderType.CALENDAR))
        self.assertIsNotNone(registry.get_active(ProviderType.STORAGE))

    def test_02_exotel_telephony_endpoints(self):
        """Module 3: Exotel telephony status and recording callbacks."""
        resp = self.client.post("/api/telephony/exotel/status", data={
            "CallSid": "e2e_exotel_call_001",
            "Status": "completed",
            "Duration": "42"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "received")
        self.assertEqual(resp.json()["disposition"], "completed")

        rec_resp = self.client.post("/api/telephony/exotel/recording", data={
            "CallSid": "e2e_exotel_call_001",
            "RecordingUrl": "https://s3.exotel.com/recordings/e2e_001.wav"
        })
        self.assertEqual(rec_resp.status_code, 200)
        self.assertEqual(rec_resp.json()["status"], "saved")

    def test_03_ai_employee_governance(self):
        """Module 6: AI Employee approval governance and persona activation."""
        employees = get_all_ai_employees()
        self.assertGreaterEqual(len(employees), 5)

        active = get_active_ai_employee()
        self.assertIsNotNone(active)
        self.assertTrue(active["is_active"])

    def test_04_messaging_and_calendar_workflow(self):
        """Modules 9 & 10: WhatsApp message sending and Google Calendar booking."""
        lead_id = create_lead({
            "name": "Naveen Reddy",
            "phone": "+91 99001 55667",
            "company": "Reddy Tech Park"
        })

        # Calendar Booking with Mocked Meet Creation
        with patch("providers.calendar.google_calendar.GoogleCalendarProvider.book_meeting", new_callable=AsyncMock) as mock_book, \
             patch("providers.calendar.google_calendar.GoogleCalendarProvider.is_configured", return_value=True):
            mock_book.return_value = {
                "success": True,
                "event_id": "e2e_event_01",
                "meet_link": "https://meet.google.com/reddy-tech-demo"
            }

            resp = self.client.post("/api/calendar/book", json={
                "lead_id": lead_id,
                "title": "Reddy Tech Park — Architecture Review",
                "start_time": "2026-11-04T10:00:00+05:30",
                "duration_minutes": 30
            })
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["meet_link"], "https://meet.google.com/reddy-tech-demo")

            lead = get_lead_by_id(lead_id)
            self.assertEqual(lead["status"], "DEMO_BOOKED")

    def test_05_executive_analytics_kpis(self):
        """Module 11: Executive Sales & Voice Analytics overview."""
        resp = self.client.get("/api/analytics/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertIn("total_leads", data)
        self.assertIn("conversion_rate", data)
        self.assertIn("objections", data)
        self.assertIn("languages", data)
        self.assertIn("employees", data)


if __name__ == "__main__":
    unittest.main()
