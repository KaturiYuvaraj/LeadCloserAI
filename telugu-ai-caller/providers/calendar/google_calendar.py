"""
Google Calendar v3 API Scheduling Provider Implementation.
Handles OAuth 2.0 Token Refresh, FreeBusy Availability, and Event Booking with Google Meet links.
"""

import os
import time
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

from providers.calendar.base import BaseCalendarProvider


class GoogleCalendarProvider(BaseCalendarProvider):
    def __init__(self):
        super().__init__(provider_name="google_calendar")
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "client_id": self.mask_secret(self.client_id),
            "client_secret": self.mask_secret(self.client_secret),
            "refresh_token": self.mask_secret(self.refresh_token),
            "calendar_id": self.calendar_id,
            "default_timezone": "Asia/Kolkata"
        }

    async def _get_access_token(self) -> Optional[str]:
        """Exchange refresh token for a live Google API access token."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not self.is_configured():
            return None

        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(token_url, data=data)
                if resp.status_code == 200:
                    token_data = resp.json()
                    self._access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self._token_expiry = time.time() + expires_in - 60
                    return self._access_token
                else:
                    logger.error(f"Google token refresh failed: {resp.text}")
                    return None
            except Exception as e:
                logger.error(f"Error refreshing Google token: {e}")
                return None

    async def check_availability(
        self,
        start_time: str,
        end_time: str,
        timezone: str = "Asia/Kolkata"
    ) -> List[Dict[str, Any]]:
        """Query Google Calendar FreeBusy endpoint."""
        token = await self._get_access_token()
        if not token:
            return []

        url = "https://www.googleapis.com/calendar/v3/freeBusy"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "timeMin": start_time,
            "timeMax": end_time,
            "timeZone": timezone,
            "items": [{"id": self.calendar_id}]
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    busy_slots = resp.json().get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
                    return busy_slots
            except Exception as e:
                logger.error(f"Error checking calendar availability: {e}")
        return []

    async def book_meeting(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 15,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Book event with Google Meet link."""
        token = await self._get_access_token()
        if not token:
            return {"success": False, "error": "Google Calendar not authenticated."}

        url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events?conferenceDataVersion=1"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Calculate end time
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except Exception:
            start_dt = datetime.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event_payload = {
            "summary": title,
            "description": description or f"Demo and scoping discussion with {customer_name or 'Client'}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "conferenceData": {
                "createRequest": {
                    "requestId": f"demo-{int(time.time())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            }
        }
        if customer_email:
            event_payload["attendees"] = [{"email": customer_email, "displayName": customer_name or "Client"}]

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=event_payload)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    meet_link = data.get("hangoutLink", "")
                    return {
                        "success": True,
                        "event_id": data.get("id"),
                        "event_link": data.get("htmlLink"),
                        "meet_link": meet_link
                    }
                return {"success": False, "error": resp.text}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Google Calendar OAuth credentials (Client ID, Secret, Refresh Token) are not configured.",
                "details": {"error": "UNCONFIGURED"}
            }

        token = await self._get_access_token()
        latency = round((time.time() - start) * 1000, 1)

        if token:
            return {
                "success": True,
                "latency_ms": latency,
                "message": f"Google Calendar API OAuth access token verified ({latency}ms).",
                "details": {"calendar_id": self.calendar_id}
            }
        else:
            return {
                "success": False,
                "latency_ms": latency,
                "message": "Failed to exchange Google OAuth refresh token for access token.",
                "details": {"error": "TOKEN_EXCHANGE_FAILED"}
            }
