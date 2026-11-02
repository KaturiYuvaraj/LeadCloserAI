"""
Legacy Twilio Telephony Provider (Preserves existing functional integration).
"""

import time
import httpx
from typing import Optional, Dict, Any
from loguru import logger

from providers.telephony.base import BaseTelephonyProvider
from services.telephony_service import telephony_service
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER


class TwilioTelephonyProvider(BaseTelephonyProvider):
    def __init__(self):
        super().__init__(provider_name="twilio")
        self.account_sid = TWILIO_ACCOUNT_SID
        self.auth_token = TWILIO_AUTH_TOKEN
        self.from_phone = TWILIO_PHONE_NUMBER

    def is_configured(self) -> bool:
        return telephony_service.is_configured()

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "account_sid": self.account_sid,
            "auth_token": self.mask_secret(self.auth_token),
            "phone_number": self.from_phone,
            "stream_endpoint": "/ws/telephony"
        }

    def generate_stream_instruction(self, host: str, lead_id: Optional[int] = None) -> str:
        return telephony_service.generate_twiml_stream(host=host, lead_id=lead_id)

    async def initiate_outbound_call(
        self,
        to_phone: str,
        lead_id: Optional[int] = None,
        callback_host: Optional[str] = None
    ) -> Dict[str, Any]:
        return await telephony_service.initiate_outbound_call(
            to_phone=to_phone,
            lead_id=lead_id,
            webhook_host=callback_host
        )

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Twilio credentials are not set in environment or integration settings.",
                "details": {"error": "UNCONFIGURED"}
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}.json"
        auth = (self.account_sid, self.auth_token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, auth=auth)
                latency = round((time.time() - start) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "message": f"Twilio account active: {data.get('friendly_name', self.account_sid)} ({latency}ms).",
                        "details": {"status": data.get("status")}
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "message": f"Twilio authentication failed (HTTP {resp.status_code}): {resp.text}",
                        "details": {"error": resp.text}
                    }
            except Exception as e:
                latency = round((time.time() - start) * 1000, 1)
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": f"Twilio connection error: {str(e)}",
                    "details": {"error": str(e)}
                }

