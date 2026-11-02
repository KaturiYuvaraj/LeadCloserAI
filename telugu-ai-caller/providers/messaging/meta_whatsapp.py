"""
Meta WhatsApp Cloud API Messaging Provider Implementation.
"""

import os
import time
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from providers.messaging.base import BaseMessagingProvider


class MetaWhatsAppProvider(BaseMessagingProvider):
    def __init__(self):
        super().__init__(provider_name="meta_whatsapp")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.business_account_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.api_version = "v19.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        return bool(self.phone_number_id and self.access_token)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "phone_number_id": self.phone_number_id,
            "business_account_id": self.business_account_id,
            "access_token": self.mask_secret(self.access_token),
            "api_version": self.api_version,
            "webhook_endpoint": "/api/webhooks/whatsapp"
        }

    def _clean_recipient_phone(self, phone: str) -> str:
        """Strip non-digits for Meta Graph API E.164 payload."""
        cleaned = "".join(filter(str.isdigit, phone))
        if len(cleaned) == 10:
            cleaned = f"91{cleaned}"
        return cleaned

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "en",
        parameters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send Meta-approved business template message (brochure, meeting confirmation).
        """
        if not self.is_configured():
            return {"success": False, "error": "WhatsApp credentials not configured."}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        recipient = self._clean_recipient_phone(to_phone)
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        if parameters:
            payload["template"]["components"] = [{
                "type": "body",
                "parameters": parameters
            }]

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    msg_id = data.get("messages", [{}])[0].get("id")
                    logger.info(f"WhatsApp template sent to {recipient}: {msg_id}")
                    return {"success": True, "message_id": msg_id}
                else:
                    logger.error(f"WhatsApp template failed ({resp.status_code}): {resp.text}")
                    return {"success": False, "error": resp.text}
            except Exception as e:
                logger.error(f"WhatsApp API error: {e}")
                return {"success": False, "error": str(e)}

    async def send_text_message(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send standard customer service message within 24-hr service window.
        """
        if not self.is_configured():
            return {"success": False, "error": "WhatsApp credentials not configured."}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        recipient = self._clean_recipient_phone(to_phone)
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": message}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    return {"success": True, "message_id": data.get("messages", [{}])[0].get("id")}
                return {"success": False, "error": resp.text}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "WhatsApp Phone Number ID or Access Token is missing in environment or settings.",
                "details": {"error": "UNCONFIGURED"}
            }

        url = f"{self.base_url}/{self.phone_number_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    display_num = data.get("display_phone_number", self.phone_number_id)
                    verified_name = data.get("verified_name", "Registered WABA")
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "message": f"Meta WhatsApp Cloud API verified for {verified_name} ({display_num}) ({latency}ms).",
                        "details": {"display_phone_number": display_num, "status": data.get("code_verification_status")}
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "message": f"WhatsApp API auth failed (HTTP {resp.status_code}): {resp.text}",
                        "details": {"error": resp.text}
                    }
            except Exception as e:
                latency = round((time.time() - start) * 1000, 1)
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": f"WhatsApp connection error: {str(e)}",
                    "details": {"error": str(e)}
                }

