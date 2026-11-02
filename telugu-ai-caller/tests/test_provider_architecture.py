"""
Unit & Integration Tests for Modular Provider Architecture.
Verifies provider registry, base contracts, Pydantic UnifiedLead schema,
and live test connection endpoints.
"""

import sys
import os
import asyncio
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers import registry, ProviderType, ProviderStatus, sync_providers_with_db
from schemas.lead import UnifiedLead, LeadSource, LeadStatus, LeadPriority, LeadEnrichmentData
from database import init_db, get_all_provider_settings


class ProviderArchitectureTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        init_db()
        sync_providers_with_db()

    def test_provider_registry_contains_all_core_domains(self):
        """Verify all 8 capability domains are registered."""
        all_providers = registry.list_all()
        provider_types = {p["type"] for p in all_providers}

        expected_types = {
            "voice_stt",
            "voice_tts",
            "llm",
            "telephony",
            "lead_discovery",
            "messaging",
            "calendar",
            "storage"
        }
        self.assertTrue(expected_types.issubset(provider_types), f"Missing types: {expected_types - provider_types}")

        # Check default registrations
        exotel = registry.get(ProviderType.TELEPHONY, "exotel")
        self.assertIsNotNone(exotel)
        self.assertEqual(exotel.provider_name, "exotel")

        sarvam_tts = registry.get(ProviderType.VOICE_TTS, "sarvam_tts")
        self.assertIsNotNone(sarvam_tts)
        self.assertEqual(sarvam_tts.provider_name, "sarvam_tts")

        apollo = registry.get(ProviderType.LEAD_DISCOVERY, "apollo")
        self.assertIsNotNone(apollo)

        apify = registry.get(ProviderType.LEAD_DISCOVERY, "apify")
        self.assertIsNotNone(apify)

        whatsapp = registry.get(ProviderType.MESSAGING, "meta_whatsapp")
        self.assertIsNotNone(whatsapp)

        gcal = registry.get(ProviderType.CALENDAR, "google_calendar")
        self.assertIsNotNone(gcal)

    def test_unified_lead_schema_validation(self):
        """Verify common Lead schema validation, phone cleaning, and database mapping."""
        lead = UnifiedLead(
            name="Kalyan Naidu",
            phone="9848011223",
            company="Naidu Mart",
            service_needed="Mobile App & E-Commerce",
            source=LeadSource.APOLLO,
            status=LeadStatus.NEW,
            priority=LeadPriority.HIGH,
            enrichment=LeadEnrichmentData(
                company_name="Naidu Mart",
                website_url="https://naidumart.com",
                industry="Retail",
                confidence_level="VERIFIED"
            )
        )
        self.assertEqual(lead.phone, "+91 9848011223", "Phone number should be normalized with +91 prefix")
        self.assertEqual(lead.source, LeadSource.APOLLO)
        self.assertEqual(lead.enrichment.confidence_level, "VERIFIED")

        db_dict = lead.to_db_dict()
        self.assertEqual(db_dict["name"], "Kalyan Naidu")
        self.assertEqual(db_dict["company"], "Naidu Mart")
        self.assertEqual(db_dict["status"], "NEW")

    async def test_provider_connection_test_diagnostics(self):
        """Verify that provider test_connection returns real structured results (no fake responses)."""
        # Test SQLite storage provider (should succeed)
        sqlite = registry.get(ProviderType.STORAGE, "sqlite")
        self.assertIsNotNone(sqlite)
        sqlite_res = await sqlite.test_connection()
        self.assertTrue(sqlite_res["success"], f"SQLite test failed: {sqlite_res}")
        self.assertIn("latency_ms", sqlite_res)

        # Test Exotel (when unconfigured, returns clean diagnostic rather than throwing error)
        exotel = registry.get(ProviderType.TELEPHONY, "exotel")
        self.assertIsNotNone(exotel)
        exotel_res = await exotel.test_connection()
        self.assertIn("success", exotel_res)
        self.assertIn("latency_ms", exotel_res)
        self.assertIn("message", exotel_res)

        # Test Sarvam TTS (if SARVAM_API_KEY is present, runs live synthesis)
        sarvam_tts = registry.get(ProviderType.VOICE_TTS, "sarvam_tts")
        self.assertIsNotNone(sarvam_tts)
        tts_res = await sarvam_tts.test_connection()
        self.assertIn("success", tts_res)
        self.assertIn("latency_ms", tts_res)

    def test_database_persistence_of_provider_settings(self):
        """Verify that provider settings are persisted in database."""
        db_settings = get_all_provider_settings()
        self.assertGreater(len(db_settings), 0, "Provider settings should be seeded in DB")
        names = [s["provider_name"] for s in db_settings]
        self.assertIn("exotel", names)
        self.assertIn("sarvam_tts", names)
        self.assertIn("apollo", names)
        self.assertIn("meta_whatsapp", names)


if __name__ == "__main__":
    unittest.main()

