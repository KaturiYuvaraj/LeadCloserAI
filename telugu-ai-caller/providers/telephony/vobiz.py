"""
Vobiz Telephony Provider Implementation.
Handles Indian PSTN Outbound and Inbound Calling over Vobiz carrier trunks with Linear16 audio streaming.
"""
import os
import time
import httpx
from typing import Optional, Dict, Any
from loguru import logger

from providers.telephony.base import BaseTelephonyProvider
from config import VOBIZ_AUTH_ID, VOBIZ_AUTH_TOKEN, VOBIZ_CALLER_ID, VOICE_PUBLIC_BASE_URL, BASE_URL


class VobizTelephonyProvider(BaseTelephonyProvider):
    def __init__(self):
        super().__init__(provider_name="vobiz")
        self.auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
        self.auth_token = os.getenv("VOBIZ_AUTH_TOKEN", VOBIZ_AUTH_TOKEN)
        self.caller_id = os.getenv("VOBIZ_CALLER_ID", VOBIZ_CALLER_ID)
        self.public_base_url = os.getenv("VOICE_PUBLIC_BASE_URL", VOICE_PUBLIC_BASE_URL)

    def is_configured(self) -> bool:
        return bool(self.auth_id and self.auth_token and self.caller_id)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "auth_id": self.auth_id,
            "auth_token": self.mask_secret(self.auth_token),
            "caller_id": self.caller_id,
            "public_base_url": self.public_base_url,
            "stream_endpoint": "/api/voice/vobiz/stream"
        }

    def generate_stream_instruction(self, host: str, lead_id: Optional[int] = None) -> str:
        clean_host = self.public_base_url or host
        clean_host = clean_host.replace("http://", "").replace("https://", "")
        ws_protocol = "wss" if ("https" in (self.public_base_url or BASE_URL)) else "ws"
        url = f"{ws_protocol}://{clean_host}/api/voice/vobiz/stream"
        if lead_id:
            url += f"?lead_id={lead_id}"
        return url

    async def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0.0,
                "message": "Vobiz credentials (VOBIZ_AUTH_ID, VOBIZ_AUTH_TOKEN, VOBIZ_CALLER_ID) not configured in .env",
                "details": {}
            }
        start = time.time()
        try:
            headers = {
                "X-Auth-ID": self.auth_id,
                "X-Auth-Token": self.auth_token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://api.vobiz.ai/api/v1/Account/{self.auth_id}/Call/",
                    headers=headers
                )
            latency = round((time.time() - start) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json() if resp.content else {}
                return {
                    "success": True,
                    "latency_ms": latency,
                    "message": f"Connected to Vobiz Carrier API. Caller ID: {self.caller_id}",
                    "details": {"status_code": resp.status_code, "caller_id": self.caller_id}
                }
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Vobiz API returned HTTP {resp.status_code}",
                "details": {"status_code": resp.status_code, "body": resp.text[:200]}
            }
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Vobiz network connection error: {str(e)}",
                "details": {"error": str(e)}
            }

    async def initiate_outbound_call(
        self,
        to_phone: str,
        lead_id: Optional[int] = None,
        callback_host: Optional[str] = None
    ) -> Dict[str, Any]:
        from voice_agent.outbound import VobizDialer, DialRequest
        dialer = VobizDialer()
        req = DialRequest(job_id=0, lead_id=lead_id or 0, to_number=to_phone)
        try:
            call_id = await dialer.dial(req)
            return {
                "success": True,
                "provider": "vobiz",
                "call_id": call_id,
                "to": to_phone,
                "from": self.caller_id
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "vobiz",
                "error": str(e)
            }
