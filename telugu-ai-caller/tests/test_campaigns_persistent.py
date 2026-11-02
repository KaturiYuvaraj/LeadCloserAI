"""
Test Suite for Phase 7: Persistent Campaign Management & Concurrency Controls.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import create_campaign, get_campaign_by_id, update_campaign_status, get_all_campaigns


class PersistentCampaignTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_create_and_fetch_campaign(self):
        """
        Verify that a campaign is stored with lead IDs, concurrency parameters, and results.
        """
        camp_id = create_campaign({
            "name": "Hyderabad Healthcare Q4 Outreach",
            "lead_ids": [1, 2, 3],
            "mode": "telephony",
            "max_concurrency": 2,
            "retry_attempts": 2
        })
        self.assertTrue(camp_id > 0)

        camp = get_campaign_by_id(camp_id)
        self.assertIsNotNone(camp)
        self.assertEqual(camp["name"], "Hyderabad Healthcare Q4 Outreach")
        self.assertEqual(camp["total_leads"], 3)
        self.assertEqual(camp["max_concurrency"], 2)

    def test_update_campaign_progress_and_logs(self):
        """
        Verify progress tracking, status transitions, and log persistence.
        """
        camp_id = create_campaign({
            "name": "Bangalore Retail Pitch",
            "lead_ids": [10, 11]
        })

        log_entry = {"time": "11:00:00", "message": "Placed call to lead 10", "level": "info"}
        results = {"demo_scheduled": 1, "closed_won": 0, "follow_up": 0, "lost": 0, "failed": 0}

        ok = update_campaign_status(
            camp_id=camp_id,
            status="running",
            completed=1,
            results=results,
            log_entry=log_entry
        )
        self.assertTrue(ok)

        camp = get_campaign_by_id(camp_id)
        self.assertEqual(camp["status"], "running")
        self.assertEqual(camp["completed_leads"], 1)
        self.assertEqual(camp["results"]["demo_scheduled"], 1)
        self.assertEqual(len(camp["logs"]), 1)
        self.assertEqual(camp["logs"][0]["message"], "Placed call to lead 10")


if __name__ == "__main__":
    unittest.main()
