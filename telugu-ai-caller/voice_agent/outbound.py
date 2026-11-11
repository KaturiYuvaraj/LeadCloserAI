"""
Outbound dialling: ask the phone provider to ring a lead and connect the answered
call to the real-time engine.

Providers (DIALER_PROVIDER = vobiz | exotel | fake; default picks the one with
credentials, else fake):

- vobiz  (also Sarvam-rented numbers): POST https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/
         with from/to/answer_url/hangup_url (X-Auth-ID / X-Auth-Token headers, per the
         official vobiz-python SDK). On answer Vobiz fetches our Answer URL, which streams
         the call to /api/voice/vobiz/stream.
- exotel: POST https://{sub_domain}/v1/Accounts/{sid}/Calls/connect.json (Basic auth).
         The lead is connected to the Exotel call flow given in EXOTEL_FLOW_URL, whose
         Voicebot applet points at /api/voice/exotel/stream. ⚠️ Confirm the field names on
         the first real call (CustomField delivery into the Voicebot start event).
- fake:  development/testing without a provider. "Rings" a simulated phone: numbers ending
         in 0 don't answer, numbers ending in 9 are busy, others answer and talk using the
         fake telephony caller and a sample WAV, then report hangup like a real provider.
"""

import asyncio
import importlib.util
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

from voice_agent import webhook_auth

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class DialRequest:
    job_id: int
    lead_id: int
    to_number: str
    language: Optional[str] = None
    max_call_seconds: int = 600
    lead_name: Optional[str] = None


class DialError(Exception):
    """The provider refused or failed to place the call."""


def public_base_url() -> str:
    """https://host the provider can reach for answer/hangup/status callbacks."""
    return os.getenv("VOICE_PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _callback_query(req: DialRequest) -> str:
    params = {"job_id": req.job_id, "lead_id": req.lead_id}
    if req.language:
        params["lang"] = req.language
    if webhook_auth.enabled():  # sent back to us on every callback and on the audio stream
        params["key"] = webhook_auth.secret()
    return urlencode(params)


class BaseDialer:
    name = "base"

    def is_configured(self) -> bool:
        return True

    async def dial(self, req: DialRequest) -> str:
        """Place the call; return the provider's call/request id."""
        raise NotImplementedError

    async def hangup(self, provider_call_id: str) -> None:
        """Best-effort hang up (used when a campaign is stopped)."""


class VobizDialer(BaseDialer):
    name = "vobiz"
    API_BASE = "https://api.vobiz.ai/api/v1/Account"

    def __init__(self):
        self.auth_id = os.getenv("VOBIZ_AUTH_ID", "")
        self.auth_token = os.getenv("VOBIZ_AUTH_TOKEN", "")
        self.caller_id = os.getenv("VOBIZ_CALLER_ID", "")

    def is_configured(self) -> bool:
        return bool(self.auth_id and self.auth_token and self.caller_id)

    def _headers(self) -> dict:
        return {"X-Auth-ID": self.auth_id, "X-Auth-Token": self.auth_token,
                "Content-Type": "application/json", "Accept": "application/json"}

    async def dial(self, req: DialRequest) -> str:
        if not self.is_configured():
            raise DialError("Vobiz is not configured (VOBIZ_AUTH_ID, VOBIZ_AUTH_TOKEN, VOBIZ_CALLER_ID)")
        query = _callback_query(req)
        body = {
            "from": self.caller_id,
            "to": req.to_number,
            "answer_url": f"{public_base_url()}/api/voice/vobiz/answer?{query}",
            "answer_method": "POST",
            "hangup_url": f"{public_base_url()}/api/voice/vobiz/hangup?{query}",
            "hangup_method": "POST",
            "ring_timeout": 45,
            "time_limit": req.max_call_seconds,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{self.API_BASE}/{self.auth_id}/Call/", json=body, headers=self._headers())
        if resp.status_code >= 300:
            raise DialError(f"Vobiz {resp.status_code}: {resp.text[:200]}")
        data = resp.json() if resp.content else {}
        return str(data.get("request_uuid") or data.get("call_uuid") or data.get("CallUUID") or "")

    async def hangup(self, provider_call_id: str) -> None:
        if not (provider_call_id and self.is_configured()):
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{self.API_BASE}/{self.auth_id}/Call/{provider_call_id}/", headers=self._headers())


class ExotelDialer(BaseDialer):
    name = "exotel"

    def __init__(self):
        self.sid = os.getenv("EXOTEL_ACCOUNT_SID", "")
        self.api_key = os.getenv("EXOTEL_API_KEY", "")
        self.api_token = os.getenv("EXOTEL_API_TOKEN", "")
        self.sub_domain = os.getenv("EXOTEL_SUB_DOMAIN", "api.exotel.com")
        self.caller_id = os.getenv("EXOTEL_CALLER_ID", "")
        self.flow_url = os.getenv("EXOTEL_FLOW_URL", "")  # http://my.exotel.com/{sid}/exoml/start_voice/{app_id}

    def is_configured(self) -> bool:
        return bool(self.sid and self.api_key and self.api_token and self.caller_id and self.flow_url)

    async def dial(self, req: DialRequest) -> str:
        if not self.is_configured():
            raise DialError("Exotel is not configured (EXOTEL_ACCOUNT_SID, EXOTEL_API_KEY, EXOTEL_API_TOKEN, "
                            "EXOTEL_CALLER_ID, EXOTEL_FLOW_URL)")
        query = _callback_query(req)
        data = {
            "From": req.to_number,
            "CallerId": self.caller_id,
            "Url": self.flow_url,
            "CustomField": query,
            "StatusCallback": f"{public_base_url()}/api/voice/exotel/status?{query}",
            "StatusCallbackEvents[0]": "terminal",
            "StatusCallbackContentType": "application/json",
            "TimeLimit": str(req.max_call_seconds),
            "TimeOut": "30",
        }
        url = f"https://{self.sub_domain}/v1/Accounts/{self.sid}/Calls/connect.json"
        async with httpx.AsyncClient(timeout=15, auth=(self.api_key, self.api_token)) as client:
            resp = await client.post(url, data=data)
        if resp.status_code >= 300:
            raise DialError(f"Exotel {resp.status_code}: {resp.text[:200]}")
        payload = resp.json() if resp.content else {}
        return str((payload.get("Call") or {}).get("Sid") or "")


class FakeDialer(BaseDialer):
    """Simulated phone network for development and tests (no provider account needed)."""

    name = "fake"

    def __init__(self):
        self.wav = os.getenv("FAKE_DIALER_WAV", str(BASE_DIR / "tests/fake_exotel/samples/three_questions.wav"))
        self.ring_seconds = float(os.getenv("FAKE_DIALER_RING_SECONDS", "2"))
        self._client_module = None
        self._pcm: Optional[bytes] = None
        self._tasks: set[asyncio.Task] = set()

    def _client(self):
        if self._client_module is None:
            path = BASE_DIR / "tests/fake_exotel/client.py"
            spec = importlib.util.spec_from_file_location("fake_telephony_client", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._client_module = module
        return self._client_module

    async def dial(self, req: DialRequest) -> str:
        call_id = f"fake-{uuid.uuid4().hex[:12]}"
        task = asyncio.create_task(self._simulate(req, call_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return call_id

    async def _report_hangup(self, req: DialRequest, call_id: str, status: str, duration: int, cause: str):
        url = f"{public_base_url()}/api/voice/vobiz/hangup?{_callback_query(req)}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, data={"CallUUID": call_id, "CallStatus": status,
                                             "Duration": str(duration), "HangupCause": cause})
        except Exception as e:
            logger.warning(f"Fake dialer could not report hangup: {e}")

    async def _simulate(self, req: DialRequest, call_id: str):
        await asyncio.sleep(self.ring_seconds)
        last_digit = req.to_number.strip()[-1:]
        if last_digit == "0":
            await asyncio.sleep(3)
            await self._report_hangup(req, call_id, "no-answer", 0, "NO_ANSWER")
            return
        if last_digit == "9":
            await self._report_hangup(req, call_id, "busy", 0, "USER_BUSY")
            return

        client = self._client()
        if self._pcm is None:
            self._pcm = await asyncio.to_thread(client.load_pcm, self.wav, client.VOBIZ_RATE)
        answer_url = f"{public_base_url()}/api/voice/vobiz/answer?{_callback_query(req)}"
        started = time.time()
        result = await client.run_call(
            url="", pcm=self._pcm, name=call_id, lead_id=None, caller=req.to_number,
            tail_seconds=3, provider="vobiz", answer_url=answer_url,
        )
        if result.error and not result.connected:
            logger.warning(f"Fake call {call_id} failed: {result.error}")
            await self._report_hangup(req, call_id, "failed", 0, "NETWORK_ERROR")
            return
        await self._report_hangup(req, call_id, "completed", int(time.time() - started), "NORMAL_CLEARING")


def get_dialer() -> BaseDialer:
    """Dialer from DIALER_PROVIDER, or the first configured provider, else the simulator."""
    choice = os.getenv("DIALER_PROVIDER", "").strip().lower()
    dialers = {"vobiz": VobizDialer, "exotel": ExotelDialer, "fake": FakeDialer}
    if choice in dialers:
        return dialers[choice]()
    for cls in (VobizDialer, ExotelDialer):
        dialer = cls()
        if dialer.is_configured():
            return dialer
    return FakeDialer()
