"""
Telephony Service for making and receiving real phone calls via Twilio / Exotel.
Handles TwiML generation, Outbound Call Triggering, and Media Streams.
"""

import os
import base64
import json
import httpx
from typing import Optional, Dict, Any
from loguru import logger

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    BASE_URL
)


class TelephonyService:
    def __init__(self):
        self.account_sid = TWILIO_ACCOUNT_SID
        self.auth_token = TWILIO_AUTH_TOKEN
        self.from_phone = TWILIO_PHONE_NUMBER

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_phone)

    def generate_twiml_stream(self, host: str, lead_id: Optional[int] = None) -> str:
        """
        Generate TwiML XML response that connects incoming or outgoing call to our WebSocket Media Stream.
        """
        ws_protocol = "wss" if "https" in BASE_URL else "ws"
        # If host starts with http/https, strip it
        clean_host = host.replace("http://", "").replace("https://", "")
        stream_url = f"{ws_protocol}://{clean_host}/ws/telephony"
        if lead_id:
            stream_url += f"?lead_id={lead_id}"

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="lead_id" value="{lead_id or ''}"/>
        </Stream>
    </Connect>
</Response>"""
        return twiml

    async def initiate_outbound_call(self, to_phone: str, lead_id: Optional[int] = None, webhook_host: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger an outbound phone call using Twilio REST API.
        """
        if not self.is_configured():
            logger.warning("Twilio credentials not configured. Outbound call cannot be initiated to real carrier.")
            return {
                "success": False,
                "error": "Twilio credentials (ACCOUNT_SID, AUTH_TOKEN, PHONE_NUMBER) not set in .env. You can use the Interactive Web Caller directly from your browser!"
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"
        auth = (self.account_sid, self.auth_token)

        host = webhook_host or BASE_URL.replace("http://", "").replace("https://", "")
        twiml_url = f"{BASE_URL}/telephony/twiml?lead_id={lead_id or ''}"

        data = {
            "To": to_phone,
            "From": self.from_phone,
            "Url": twiml_url,
            "Method": "POST"
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, data=data, auth=auth)
                if resp.status_code in [200, 201]:
                    call_info = resp.json()
                    logger.info(f"Outbound call initiated successfully: SID {call_info.get('sid')}")
                    return {
                        "success": True,
                        "call_sid": call_info.get("sid"),
                        "status": call_info.get("status")
                    }
                else:
                    logger.error(f"Twilio call failed: {resp.status_code} - {resp.text}")
                    return {
                        "success": False,
                        "error": resp.text
                    }
            except Exception as e:
                logger.error(f"Error calling Twilio API: {e}")
                return {"success": False, "error": str(e)}


telephony_service = TelephonyService()

