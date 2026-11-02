"""Offline API tests for the CRM surface.

Tests use an isolated SQLite database and do not call Sarvam or a telephony
provider. Run with: python -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

import database
from database import init_db
from main import app
from services.telephony_service import telephony_service


class CrmApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        self.original_db_file = database.DB_FILE
        database.DB_FILE = self.database_path
        init_db()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        database.DB_FILE = self.original_db_file
        self.temporary_directory.cleanup()

    async def test_create_read_and_update_lead(self) -> None:
        created = await self.client.post(
            "/api/leads",
            json={
                "name": "Ravi Kumar",
                "phone": "+919999999999",
                "company": "Example Stores",
                "service_needed": "Website",
            },
        )
        self.assertEqual(created.status_code, 200)
        lead_id = created.json()["lead_id"]

        fetched = await self.client.get(f"/api/leads/{lead_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["lead"]["name"], "Ravi Kumar")

        updated = await self.client.put(
            f"/api/leads/{lead_id}", json={"status": "QUALIFIED", "budget": "50000"}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["success"])

    async def test_missing_lead_returns_404(self) -> None:
        response = await self.client.get("/api/leads/99999")
        self.assertEqual(response.status_code, 404)

    async def test_outbound_call_passes_through_to_provider_adapter(self) -> None:
        original = telephony_service.initiate_outbound_call
        telephony_service.initiate_outbound_call = AsyncMock(
            return_value={"success": False, "error": "Provider not configured"}
        )
        try:
            response = await self.client.post(
                "/api/call/outbound", json={"phone": "+919999999999", "lead_id": 1}
            )
        finally:
            telephony_service.initiate_outbound_call = original

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    async def test_twiml_uses_the_telephony_stream(self) -> None:
        response = await self.client.post("/telephony/twiml?lead_id=7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("/ws/telephony?lead_id=7", response.text)
