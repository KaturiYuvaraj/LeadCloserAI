"""
Sarvam health: stop calling when Sarvam can't serve calls (credits finished or key rejected).

Without Sarvam the AI can't hear, think or speak, so a call that connects would leave the
customer in silence. Any Sarvam error that means "out of credits" (HTTP 402, insufficient
quota) or "key rejected" (HTTP 401/403) blocks calling:
  - the live call ends at once and its lead goes back in the queue (voice_agent/session.py)
  - the dialer places no new calls while blocked (voice_agent/dialer.py)
  - the dashboard shows a banner (GET /api/dialer/status → "service_block")
Every PROBE_EVERY_SECS the dialer sends Sarvam a tiny request (a fraction of a paisa); once it
succeeds, or someone presses Resume, calling continues.
"""

import os
import re
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger

PROBE_EVERY_SECS = int(os.getenv("SARVAM_PROBE_EVERY_SECS", "600"))

_CREDITS = re.compile(r"\b402\b|insufficient[_ ]quota|no credits|out of credits|quota exceeded|payment required", re.I)
_AUTH = re.compile(r"\b40[13]\b.*(auth|credential|api[_ ]?key|subscription)|invalid[_ ]api[_ ]key|"
                   r"invalid or missing authentication", re.I)

MESSAGES = {
    "no_credits": "Sarvam credits finished. Top up at dashboard.sarvam.ai; calling resumes automatically.",
    "invalid_key": "Sarvam rejected the API key. Check SARVAM_API_KEY in .env, then press Resume.",
}

_block: Optional[Dict[str, Any]] = None
_last_probe = 0.0


def classify(error: str) -> Optional[str]:
    """'no_credits', 'invalid_key' or None for an error message from a Sarvam service."""
    text = str(error or "")
    if _CREDITS.search(text):
        return "no_credits"
    if _AUTH.search(text):
        return "invalid_key"
    return None


def report_error(error: str, where: str = "") -> Optional[str]:
    """Block calling if `error` means Sarvam can't serve calls. Returns the reason, or None."""
    global _block
    reason = classify(error)
    if reason and not _block:
        _block = {"reason": reason, "message": MESSAGES[reason], "since": time.time(), "where": where}
        logger.error(f"⛔ Calling blocked: {MESSAGES[reason]} ({where}: {str(error)[:160]})")
    return reason


def blocked() -> Optional[Dict[str, Any]]:
    return dict(_block) if _block else None


def clear(why: str = "manual") -> None:
    global _block
    if _block:
        logger.info(f"✅ Calling unblocked ({why})")
    _block = None


def probe_due(now: Optional[float] = None) -> bool:
    return bool(_block) and (now or time.time()) - _last_probe >= PROBE_EVERY_SECS


async def probe(now: Optional[float] = None) -> bool:
    """Tiny Sarvam request; unblocks calling when it succeeds. Returns True if Sarvam works."""
    global _last_probe
    _last_probe = now or time.time()
    key = os.getenv("SARVAM_API_KEY", "").strip()
    base = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{base}/v1/chat/completions", headers={"api-subscription-key": key},
                                     json={"model": "sarvam-105b-conversations", "max_tokens": 1,
                                           "messages": [{"role": "user", "content": "hi"}]})
    except httpx.HTTPError as e:
        logger.warning(f"Sarvam probe failed: {type(e).__name__}")
        return False
    if resp.status_code == 200:
        clear("Sarvam is working again")
        return True
    logger.info(f"Sarvam still unavailable (HTTP {resp.status_code})")
    return False
