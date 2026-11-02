"""
Test Suite for Phase 3: Apollo & Apify Lead Discovery and Enrichment Integration.
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
    record_provider_usage,
    get_daily_provider_usage,
    update_lead_enrichment
)
from providers import registry, ProviderType
from schemas.lead import UnifiedLead, LeadSource, LeadStatus, LeadPriority, LeadEnrichmentData


class LeadDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_unconfigured_discovery_returns_clean_guidance(self):
        """
        Verify that attempting to discover leads with an unconfigured provider
        returns HTTP 400 with actionable configuration instructions (no crash).
        """
        resp = self.client.post("/api/leads/discover", json={
            "provider": "apollo",
            "filters": {"industries": ["Healthcare"], "locations": ["Hyderabad"]},
            "limit": 5
        })
        # If unconfigured, returns 400 with error message explaining where to configure
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("not configured", data["error"])

    def test_invalid_provider_returns_400(self):
        resp = self.client.post("/api/leads/discover", json={
            "provider": "unknown_scout",
            "filters": {}
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not found", resp.json()["detail"])

    def test_import_discovered_leads(self):
        """
        Verify that discovered leads can be bulk imported into the CRM pipeline.
        """
        test_leads = [
            {
                "name": "Dr. Ramesh Chandra",
                "phone": "+91 9848011223",
                "email": "ramesh@chandrahospital.in",
                "company": "Chandra Multi-Specialty Clinics",
                "designation": "Managing Director",
                "industry": "Healthcare",
                "location": "Hyderabad, Telangana",
                "service_needed": "Automated WhatsApp Booking System",
                "budget": "₹75,000",
                "source": "apollo",
                "status": "NEW"
            },
            {
                "name": "Priya Reddy",
                "phone": "+91 9440055667",
                "email": "priya@reddywarehousing.com",
                "company": "Reddy Freight & Warehousing",
                "designation": "Operations VP",
                "industry": "Logistics",
                "location": "Vijayawada, AP",
                "service_needed": "Fleet Management Mobile App",
                "budget": "₹1,50,000",
                "source": "apify",
                "status": "NEW"
            }
        ]

        resp = self.client.post("/api/leads/discover/import", json={"leads": test_leads})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["imported_count"], 2)

    def test_provider_usage_and_daily_guard(self):
        """
        Verify that API credit tracking logs usage and returns correct daily totals.
        """
        initial_usage = get_daily_provider_usage("apollo_test")
        record_provider_usage("apollo_test", "mixed_people/search", credits_used=3.5, details="Test search 1")
        record_provider_usage("apollo_test", "organizations/enrich", credits_used=1.0, details="Test enrich 1")

        new_usage = get_daily_provider_usage("apollo_test")
        self.assertAlmostEqual(new_usage - initial_usage, 4.5, places=1)

    def test_lead_enrichment_persistence(self):
        """
        Verify that enrichment data (tech stack, social profiles) persists to SQLite.
        """
        lead_id = create_lead({
            "name": "Vikram Sethi",
            "phone": "+91 9848099887",
            "company": "Sethi Retail Mart",
            "service_needed": "E-Commerce App"
        })

        enrichment_dict = {
            "company_name": "Sethi Retail Mart Pvt Ltd",
            "website_url": "https://sethiretail.in",
            "industry": "Supermarkets & Retail",
            "technologies_detected": ["Shopify E-Commerce", "React / Next.js", "Razorpay Payments"],
            "social_profiles": {"linkedin": "https://linkedin.com/company/sethi-retail"},
            "confidence_level": "VERIFIED"
        }

        updated = update_lead_enrichment(lead_id, enrichment_dict, extra={"industry": "Supermarkets & Retail"})
        self.assertTrue(updated)

        saved_lead = get_lead_by_id(lead_id)
        self.assertIsNotNone(saved_lead)
        self.assertEqual(saved_lead["industry"], "Supermarkets & Retail")
        self.assertIn("Shopify", saved_lead["enrichment_data"])


if __name__ == "__main__":
    unittest.main()

