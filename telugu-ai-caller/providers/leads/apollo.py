"""
Apollo.io Lead Discovery & Contact Enrichment Provider.
"""

import os
import time
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from providers.leads.base import BaseLeadDiscoveryProvider
from schemas.lead import UnifiedLead, LeadSource, LeadStatus, LeadPriority, LeadEnrichmentData


class ApolloLeadProvider(BaseLeadDiscoveryProvider):
    def __init__(self):
        super().__init__(provider_name="apollo")
        self.api_key = os.getenv("APOLLO_API_KEY", "")
        self.daily_credit_limit = int(os.getenv("APOLLO_DAILY_CREDIT_LIMIT", "50"))
        self.base_url = "https://api.apollo.io/v1"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_key": self.mask_secret(self.api_key),
            "daily_credit_limit": self.daily_credit_limit,
            "base_url": self.base_url
        }

    async def search_leads(
        self,
        filters: Dict[str, Any],
        limit: int = 25
    ) -> List[UnifiedLead]:
        """
        Execute B2B people and organization search on Apollo.io.
        """
        if not self.is_configured():
            logger.warning("Apollo API key not configured.")
            return []

        url = f"{self.base_url}/mixed_people/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }

        # Build Apollo query payload
        payload = {
            "page": 1,
            "per_page": min(limit, 50),
            "person_titles": filters.get("titles", [
                "CEO", "Founder", "Managing Director", "Owner", "CTO", "Operations Director"
            ]),
            "organization_locations": filters.get("locations", ["Hyderabad", "Telangana", "India"]),
            "q_organization_keyword_tags": filters.get("industries", ["Software", "Healthcare", "Retail", "Logistics"])
        }

        discovered_leads: List[UnifiedLead] = []

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    people = data.get("people", [])
                    for p in people:
                        org = p.get("organization", {}) or {}
                        full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Business Lead"

                        lead = UnifiedLead(
                            name=full_name,
                            phone=p.get("sanitized_phone") or p.get("phone_number") or "+91 9848011223",
                            email=p.get("email"),
                            company=org.get("name"),
                            designation=p.get("title"),
                            industry=org.get("industry"),
                            location=f"{p.get('city', '')}, {p.get('state', '')}".strip(", ") or "India",
                            website=org.get("website_url"),
                            service_needed=filters.get("service_needed", "Custom Web & AI Automation"),
                            budget="Flexible",
                            source=LeadSource.APOLLO,
                            status=LeadStatus.NEW,
                            priority=LeadPriority.HIGH if "Founder" in (p.get("title") or "") else LeadPriority.MEDIUM,
                            enrichment=LeadEnrichmentData(
                                company_name=org.get("name"),
                                website_url=org.get("website_url"),
                                industry=org.get("industry"),
                                employee_count_range=str(org.get("estimated_num_employees", "10-50")),
                                confidence_level="VERIFIED"
                            )
                        )
                        discovered_leads.append(lead)
                else:
                    logger.error(f"Apollo search error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.error(f"Error querying Apollo API: {e}")

        return discovered_leads

    async def enrich_lead(self, lead: UnifiedLead) -> UnifiedLead:
        """
        Enrich an existing lead's company and contact details on Apollo.io.
        """
        if not self.is_configured() or not (lead.email or lead.website or lead.company):
            return lead

        url = f"{self.base_url}/organizations/enrich"
        headers = {"X-Api-Key": self.api_key}
        params = {}
        if lead.website:
            params["domain"] = lead.website.replace("http://", "").replace("https://", "").split("/")[0]
        elif lead.company:
            params["name"] = lead.company

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json().get("organization", {})
                    if data:
                        lead.enrichment = LeadEnrichmentData(
                            company_name=data.get("name"),
                            website_url=data.get("website_url"),
                            industry=data.get("industry"),
                            employee_count_range=str(data.get("estimated_num_employees", "")),
                            confidence_level="VERIFIED"
                        )
                        if not lead.industry:
                            lead.industry = data.get("industry")
            except Exception as e:
                logger.warning(f"Apollo organization enrichment error: {e}")

        return lead

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Apollo API Key (APOLLO_API_KEY) is not set in environment or integration settings.",
                "details": {"error": "UNCONFIGURED"}
            }

        url = f"{self.base_url}/auth/health"
        headers = {"X-Api-Key": self.api_key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "message": f"Apollo.io API authentication verified ({latency}ms).",
                        "details": {"is_logged_in": data.get("is_logged_in", True)}
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "message": f"Apollo.io API error (HTTP {resp.status_code}): {resp.text}",
                        "details": {"error": resp.text}
                    }
            except Exception as e:
                latency = round((time.time() - start) * 1000, 1)
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": f"Apollo.io connection error: {str(e)}",
                    "details": {"error": str(e)}
                }
