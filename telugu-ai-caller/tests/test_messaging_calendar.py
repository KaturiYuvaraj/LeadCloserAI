"""
Test Suite for Modules 9 & 10: Meta WhatsApp Cloud API and Google Calendar API.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import create_lead, get_lead_by_id


class MessagingAndCalendarTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_whatsapp_webhook_verification(self):
        """
        Verify Meta webhook challenge verification handshake.
        """
        resp = self.client.get("/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=sp_associates_leadcloser_webhook&hub.challenge=CHALLENGE_CODE_123")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "CHALLENGE_CODE_123")

    def test_whatsapp_webhook_inbound_message(self):
        """
        Verify inbound WhatsApp reply associates with lead and appends note.
        """
        lead_id = create_lead({
            "name": "Kiran Kumar",
            "phone": "+91 9988776655",
            "company": "Kiran Enterprises"
        })

        webhook_payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "919988776655",
                            "text": {"body": "Yes, please schedule the demo call tomorrow at 11am."}
                        }]
                    }
                }]
            }]
        }

        resp = self.client.post("/api/webhooks/whatsapp", json=webhook_payload)
        self.assertEqual(resp.status_code, 200)

        updated_lead = get_lead_by_id(lead_id)
        self.assertIn("Yes, please schedule the demo", updated_lead["notes"])

    def test_whatsapp_send_unconfigured_guidance(self):
        """
        Verify unconfigured WhatsApp credentials return clean HTTP 400 with setup guidance.
        """
        resp = self.client.post("/api/messaging/whatsapp/send", json={
            "phone": "+91 9848011223",
            "message": "Hello from S P Associates!"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not configured", resp.json()["error"])

    def test_calendar_booking_with_mocked_oauth(self):
        """
        Verify that booking meeting sets lead status to DEMO_BOOKED and saves Google Meet link.
        """
        lead_id = create_lead({
            "name": "Anil Varma",
            "email": "anil@varmafarms.com",
            "phone": "+91 9848033445"
        })

        # Mock the Google Calendar provider book_meeting method
        with patch("providers.calendar.google_calendar.GoogleCalendarProvider.book_meeting", new_callable=AsyncMock) as mock_book, \
             patch("providers.calendar.google_calendar.GoogleCalendarProvider.is_configured", return_value=True):
            mock_book.return_value = {
                "success": True,
                "event_id": "google_event_999",
                "meet_link": "https://meet.google.com/abc-defg-hij"
            }

            resp = self.client.post("/api/calendar/book", json={
                "lead_id": lead_id,
                "title": "S P Associates — Software Demo",
                "start_time": "2026-11-03T11:00:00+05:30",
                "duration_minutes": 15
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["meet_link"], "https://meet.google.com/abc-defg-hij")

            # Verify lead updated to DEMO_BOOKED
            updated_lead = get_lead_by_id(lead_id)
            self.assertEqual(updated_lead["status"], "DEMO_BOOKED")
            self.assertIn("meet.google.com", updated_lead["action_items"])


if __name__ == "__main__":
    unittest.main()

