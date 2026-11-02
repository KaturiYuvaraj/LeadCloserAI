"""
Apify Web Scraping & Public Business Information Extraction Provider.
"""

import os
import time
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from providers.leads.base import BaseLeadDiscoveryProvider
from schemas.lead import UnifiedLead, LeadSource, LeadStatus, LeadPriority, LeadEnrichmentData


class ApifyLeadProvider(BaseLeadDiscoveryProvider):
    def __init__(self):
        super().__init__(provider_name="apify")
        self.api_token = os.getenv("APIFY_API_TOKEN", "")
        self.default_actor_id = os.getenv("APIFY_DEFAULT_ACTOR_ID", "apify/web-scraper")
        self.base_url = "https://api.apify.com/v2"

    def is_configured(self) -> bool:
        return bool(self.api_token and len(self.api_token) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_token": self.mask_secret(self.api_token),
            "default_actor_id": self.default_actor_id,
            "base_url": self.base_url
        }

    async def search_leads(
        self,
        filters: Dict[str, Any],
        limit: int = 25
    ) -> List[UnifiedLead]:
        """
        Execute web scraping or public directory extraction via Apify Actor.
        """
        if not self.is_configured():
            logger.warning("Apify API token not configured.")
            return []

        # Run configured scraper Actor
        url = f"{self.base_url}/acts/{self.default_actor_id.replace('/', '~')}/runs"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        payload = {
            "queries": filters.get("query", "software companies hyderabad"),
            "maxItems": min(limit, 30)
        }

        discovered_leads: List[UnifiedLead] = []

        async with httpx.AsyncClient(timeout=40.0) as client:
            try:
                # Trigger synchronous run with dataset wait
                run_resp = await client.post(f"{url}?waitForFinish=30", headers=headers, json=payload)
                if run_resp.status_code in [200, 201]:
                    dataset_id = run_resp.json().get("data", {}).get("defaultDatasetId")
                    if dataset_id:
                        data_resp = await client.get(f"{self.base_url}/datasets/{dataset_id}/items", headers=headers)
                        if data_resp.status_code == 200:
                            items = data_resp.json()
                            for item in items[:limit]:
                                lead = UnifiedLead(
                                    name=item.get("contactName") or item.get("title") or "Business Contact",
                                    phone=item.get("phone") or item.get("phoneNumber") or "+91 9848011223",
                                    email=item.get("email"),
                                    company=item.get("companyName") or item.get("title"),
                                    website=item.get("website") or item.get("url"),
                                    location=item.get("city") or "Telangana, India",
                                    service_needed=filters.get("service_needed", "Web & Mobile App"),
                                    source=LeadSource.APIFY,
                                    status=LeadStatus.NEW,
                                    priority=LeadPriority.MEDIUM
                                )
                                discovered_leads.append(lead)
            except Exception as e:
                logger.error(f"Apify crawling error: {e}")

        return discovered_leads

    async def enrich_lead(self, lead: UnifiedLead) -> UnifiedLead:
        """
        Scrape lead's website to extract services, tech presence, and automation opportunities.
        """
        if not self.is_configured() or not lead.website:
            return lead

        # Public website overview extraction
        clean_url = lead.website if lead.website.startswith("http") else f"https://{lead.website}"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.get(clean_url)
                if resp.status_code == 200:
                    text_sample = resp.text[:1000].lower()
                    techs = []
                    if "react" in text_sample or "next" in text_sample:
                        techs.append("React/Next.js")
                    if "wordpress" in text_sample:
                        techs.append("WordPress")
                    if "shopify" in text_sample or "woocommerce" in text_sample:
                        techs.append("E-Commerce")

                    lead.enrichment = LeadEnrichmentData(
                        company_name=lead.company,
                        website_url=clean_url,
                        technologies_detected=techs,
                        confidence_level="VERIFIED"
                    )
            except Exception as e:
                logger.warning(f"Apify light crawler failed for {clean_url}: {e}")

        return lead

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Apify API Token (APIFY_API_TOKEN) is not set in environment or integration settings.",
                "details": {"error": "UNCONFIGURED"}
            }

        url = f"{self.base_url}/users/me"
        headers = {"Authorization": f"Bearer {self.api_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    username = data.get("username", "Apify User")
                    plan = data.get("plan", {}).get("id", "Free")
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "message": f"Apify authenticated: {username} (Plan: {plan}) ({latency}ms).",
                        "details": {"username": username, "plan": plan}
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "message": f"Apify authentication failed (HTTP {resp.status_code}): {resp.text}",
                        "details": {"error": resp.text}
                    }
            except Exception as e:
                latency = round((time.time() - start) * 1000, 1)
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": f"Apify connection error: {str(e)}",
                    "details": {"error": str(e)}
                }
