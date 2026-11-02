import os
import sys
import asyncio
import unittest
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import app


class ProviderEndpointTests(unittest.IsolatedAsyncioTestCase):

    async def test_get_providers_endpoint(self):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/integrations/providers")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("providers", data)
            providers = data["providers"]
            names = [p["name"] for p in providers]
            self.assertIn("sarvam_tts", names)
            self.assertIn("exotel", names)
            self.assertIn("apollo", names)
            self.assertIn("apify", names)
            self.assertIn("meta_whatsapp", names)
            self.assertIn("google_calendar", names)

    async def test_provider_test_endpoint(self):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Test Exotel (should return structured result with UNCONFIGURED message if unconfigured)
            resp = await client.post("/api/integrations/providers/telephony/exotel/test")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("result", data)
            self.assertIn("latency_ms", data["result"])
            self.assertIn("message", data["result"])

    async def test_provider_update_endpoint(self):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/integrations/providers/leads/apollo",
                json={"is_enabled": True, "config": {"daily_credit_limit": 75}}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()

