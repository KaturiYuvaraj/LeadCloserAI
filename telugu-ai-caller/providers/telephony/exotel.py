"""
Exotel Telephony Provider Implementation.
Handles Indian PSTN Outbound Calling and Exotel AgentStream WebSockets.
"""

import os
import time
import httpx
from typing import Optional, Dict, Any
from loguru import logger

from providers.telephony.base import BaseTelephonyProvider
from config import BASE_URL


class ExotelTelephonyProvider(BaseTelephonyProvider):
    def __init__(self):
        super().__init__(provider_name="exotel")
        self.account_sid = os.getenv("EXOTEL_ACCOUNT_SID", "")
        self.api_key = os.getenv("EXOTEL_API_KEY", "")
        self.api_token = os.getenv("EXOTEL_API_TOKEN", "")
        self.sub_domain = os.getenv("EXOTEL_SUB_DOMAIN", "api.exotel.com")
        self.caller_id = os.getenv("EXOTEL_CALLER_ID", "")

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.api_key and self.api_token and self.caller_id)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "account_sid": self.account_sid,
            "api_key": self.mask_secret(self.api_key),
            "api_token": self.mask_secret(self.api_token),
            "sub_domain": self.sub_domain,
            "caller_id": self.caller_id,
            "stream_endpoint": "/api/telephony/exotel/stream"
        }

    def generate_stream_instruction(self, host: str, lead_id: Optional[int] = None) -> str:
        """
        Generate Exotel AgentStream instruction payload or Applet response.
        """
        ws_protocol = "wss" if "https" in BASE_URL else "ws"
        clean_host = host.replace("http://", "").replace("https://", "")
        stream_url = f"{ws_protocol}://{clean_host}/api/telephony/exotel/stream"
        if lead_id:
            stream_url += f"?lead_id={lead_id}"
        return stream_url

    async def initiate_outbound_call(
        self,
        to_phone: str,
        lead_id: Optional[int] = None,
        callback_host: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger outbound PSTN call via Exotel Connect Voice AI API.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Exotel credentials (EXOTEL_ACCOUNT_SID, EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_CALLER_ID) are not set in environment or integration settings."
            }

        url = f"https://{self.sub_domain}/v1/Accounts/{self.account_sid}/Calls/connect.json"
        auth = (self.api_key, self.api_token)

        host = callback_host or BASE_URL.replace("http://", "").replace("https://", "")
        stream_url = self.generate_stream_instruction(host, lead_id)

        data = {
            "From": to_phone,
            "CallerId": self.caller_id,
            "Url": f"{BASE_URL}/api/telephony/exotel/status?lead_id={lead_id or ''}",
            "CustomField": str(lead_id or ""),
            "StatusCallback": f"{BASE_URL}/api/telephony/exotel/status",
            "StatusCallbackEvents[0]": "terminal"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, data=data, auth=auth)
                if resp.status_code in [200, 201]:
                    call_info = resp.json().get("Call", {})
                    logger.info(f"Exotel PSTN call initiated: SID {call_info.get('Sid')}")
                    return {
                        "success": True,
                        "call_sid": call_info.get("Sid"),
                        "status": call_info.get("Status"),
                        "stream_url": stream_url
                    }
                else:
                    logger.error(f"Exotel call failed ({resp.status_code}): {resp.text}")
                    return {
                        "success": False,
                        "error": resp.text
                    }
            except Exception as e:
                logger.error(f"Error calling Exotel API: {e}")
                return {"success": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Exotel credentials (SID, Key, Token, CallerId) are not configured.",
                "details": {"error": "UNCONFIGURED"}
            }

        url = f"https://{self.sub_domain}/v1/Accounts/{self.account_sid}.json"
        auth = (self.api_key, self.api_token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, auth=auth)
                latency = round((time.time() - start) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    acc = data.get("Account", {})
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "message": f"Exotel account verified: {acc.get('FriendlyName', self.account_sid)} ({latency}ms).",
                        "details": {"status": acc.get("Status", "active")}
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "message": f"Exotel authentication failed (HTTP {resp.status_code}): {resp.text}",
                        "details": {"error": resp.text}
                    }
            except Exception as e:
                latency = round((time.time() - start) * 1000, 1)
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": f"Exotel connection error: {str(e)}",
                    "details": {"error": str(e)}
                }

