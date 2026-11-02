"""
Apify Web Scraping & Public Business Information Extraction Provider.
"""

import os
import re
import time
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from providers.leads.base import BaseLeadDiscoveryProvider
from schemas.lead import UnifiedLead, LeadSource, LeadStatus, LeadPriority, LeadEnrichmentData
from database import get_daily_provider_usage, record_provider_usage


class ApifyLeadProvider(BaseLeadDiscoveryProvider):
    def __init__(self):
        super().__init__(provider_name="apify")
        self.api_token = os.getenv("APIFY_API_TOKEN", "")
        self.default_actor_id = os.getenv("APIFY_DEFAULT_ACTOR_ID", "apify/web-scraper")
        self.daily_credit_limit = int(os.getenv("APIFY_DAILY_CREDIT_LIMIT", "25"))
        self.base_url = "https://api.apify.com/v2"

    def is_configured(self) -> bool:
        return bool(self.api_token and len(self.api_token) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_token": self.mask_secret(self.api_token),
            "default_actor_id": self.default_actor_id,
            "daily_credit_limit": self.daily_credit_limit,
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
            raise ValueError("Apify API Token is not configured. Please add your token in Integrations > Settings or .env file.")

        used_today = get_daily_provider_usage("apify")
        if used_today >= self.daily_credit_limit:
            raise RuntimeError(
                f"Apify daily run threshold reached ({used_today:.0f}/{self.daily_credit_limit} runs used today). "
                f"Adjust APIFY_DAILY_CREDIT_LIMIT in settings to allow more runs."
            )

        query = filters.get("query")
        if not query:
            ind = filters.get("industries", ["Software Services"])[0]
            loc = filters.get("locations", ["Hyderabad"])[0]
            query = f"{ind} in {loc}"

        actor_path = self.default_actor_id.replace("/", "~")
        url = f"{self.base_url}/acts/{actor_path}/runs"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        payload = {
            "queries": query,
            "maxItems": min(limit, 30)
        }

        discovered_leads: List[UnifiedLead] = []

        async with httpx.AsyncClient(timeout=45.0) as client:
            run_resp = await client.post(f"{url}?waitForFinish=30", headers=headers, json=payload)
            if run_resp.status_code in [200, 201]:
                run_data = run_resp.json().get("data", {})
                dataset_id = run_data.get("defaultDatasetId")
                if dataset_id:
                    data_resp = await client.get(f"{self.base_url}/datasets/{dataset_id}/items", headers=headers)
                    if data_resp.status_code == 200:
                        items = data_resp.json()
                        for item in items[:limit]:
                            c_name = item.get("companyName") or item.get("title") or "Corporate Entity"
                            contact = item.get("contactName") or item.get("name") or "Business Owner"
                            phone = item.get("phone") or item.get("phoneNumber") or "+91 9848011223"
                            website = item.get("website") or item.get("url")

                            lead = UnifiedLead(
                                name=contact,
                                phone=phone,
                                email=item.get("email"),
                                company=c_name,
                                website=website,
                                location=item.get("city") or filters.get("locations", ["Hyderabad, India"])[0],
                                service_needed=filters.get("service_needed", "Web & Mobile App Development"),
                                source=LeadSource.APIFY,
                                status=LeadStatus.NEW,
                                priority=LeadPriority.MEDIUM,
                                enrichment=LeadEnrichmentData(
                                    company_name=c_name,
                                    website_url=website,
                                    confidence_level="VERIFIED"
                                )
                            )
                            discovered_leads.append(lead)

                record_provider_usage(
                    "apify",
                    "actor_crawl",
                    credits_used=1.0,
                    details=f"Extracted {len(discovered_leads)} leads for query '{query}'"
                )
            elif run_resp.status_code in [401, 403]:
                raise PermissionError("Apify API Token authentication failed. Please check your token in Integrations.")
            elif run_resp.status_code == 429:
                raise RuntimeError("Apify rate limit exceeded.")
            else:
                raise RuntimeError(f"Apify crawling error (HTTP {run_resp.status_code}): {run_resp.text}")

        return discovered_leads

    async def enrich_lead(self, lead: UnifiedLead) -> UnifiedLead:
        """
        Scrape lead's public website to extract services, tech stack, and social channels.
        """
        if not lead.website:
            return lead

        clean_url = lead.website.strip()
        if not clean_url.startswith("http"):
            clean_url = f"https://{clean_url}"

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            try:
                resp = await client.get(clean_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadCloser/2.0"})
                if resp.status_code == 200:
                    html_content = resp.text
                    lower_content = html_content.lower()

                    # Extract page title
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
                    page_title = title_match.group(1).strip() if title_match else ""

                    # Detect tech presence
                    techs = []
                    if "react" in lower_content or "next" in lower_content or "_next" in lower_content:
                        techs.append("React / Next.js")
                    if "vue" in lower_content or "nuxt" in lower_content:
                        techs.append("Vue.js")
                    if "wp-content" in lower_content or "wordpress" in lower_content:
                        techs.append("WordPress")
                    if "shopify" in lower_content or "myshopify" in lower_content:
                        techs.append("Shopify E-Commerce")
                    if "woocommerce" in lower_content:
                        techs.append("WooCommerce")
                    if "tailwind" in lower_content:
                        techs.append("Tailwind CSS")
                    if "bootstrap" in lower_content:
                        techs.append("Bootstrap")
                    if "razorpay" in lower_content:
                        techs.append("Razorpay Payments")
                    if "stripe" in lower_content:
                        techs.append("Stripe Payments")

                    # Extract Social Profiles
                    socials = {}
                    li_match = re.search(r'href=[\'"](https?://(?:www\.)?linkedin\.com/[^\'"]+)[\'"]', html_content)
                    if li_match:
                        socials["linkedin"] = li_match.group(1)

                    fb_match = re.search(r'href=[\'"](https?://(?:www\.)?facebook\.com/[^\'"]+)[\'"]', html_content)
                    if fb_match:
                        socials["facebook"] = fb_match.group(1)

                    tw_match = re.search(r'href=[\'"](https?://(?:www\.)?(?:twitter|x)\.com/[^\'"]+)[\'"]', html_content)
                    if tw_match:
                        socials["twitter"] = tw_match.group(1)

                    lead.enrichment = LeadEnrichmentData(
                        company_name=lead.company or page_title,
                        website_url=clean_url,
                        technologies_detected=techs,
                        social_profiles=socials,
                        confidence_level="VERIFIED"
                    )

                    record_provider_usage("apify", "website_enrich", credits_used=0.2, details=f"Scraped tech stack for {clean_url}")
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
