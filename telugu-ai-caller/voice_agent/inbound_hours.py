"""
When the AI answers incoming calls.

Set on the dashboard's Inbound page and kept in inbound_hours.json, so it survives a restart.
Inside the hours the AI answers; outside them the call is forwarded to the team's number.
The hours may cross midnight: 20:00 to 10:00 means 8 PM to 10 AM the next morning.
With no transfer number, or the schedule switched off, the AI answers every call.
"""

import json
import os
import re
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from voice_agent.rules import IST

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULTS: Dict[str, Any] = {"enabled": False, "start": "20:00", "end": "10:00", "transfer_number": ""}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PHONE = re.compile(r"^\+\d{10,15}$")


def _file() -> Path:
    return Path(os.getenv("INBOUND_HOURS_FILE") or BASE_DIR / "inbound_hours.json")


def _clean_phone(value: Any) -> str:
    digits = re.sub(r"[^\d+]", "", str(value or ""))
    if digits and not digits.startswith("+"):
        digits = "+91" + digits[-10:] if len(digits) >= 10 else digits
    return digits


def get_settings() -> Dict[str, Any]:
    try:
        saved = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    out = dict(DEFAULTS)
    if isinstance(saved, dict):
        out.update({k: saved[k] for k in DEFAULTS if k in saved})
    return out


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check and store the dashboard's settings. Raises ValueError with a message for the page."""
    enabled = bool(data.get("enabled"))
    start, end = str(data.get("start") or "").strip(), str(data.get("end") or "").strip()
    if not _HHMM.match(start) or not _HHMM.match(end):
        raise ValueError("Pick a 'from' and 'to' time.")
    if start == end:
        raise ValueError("'From' and 'to' can't be the same time. Switch the schedule off to answer all day.")
    number = _clean_phone(data.get("transfer_number"))
    if number and not _PHONE.match(number):
        raise ValueError("Enter the transfer number with country code, e.g. +91 77802 36242.")
    if enabled and not number:
        raise ValueError("Add the team's number: calls outside these hours are forwarded to it.")
    settings = {"enabled": enabled, "start": start, "end": end, "transfer_number": number}
    _file().write_text(json.dumps(settings), encoding="utf-8")
    return settings


def _hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def in_ai_hours(settings: Dict[str, Any], now_utc: Optional[datetime] = None) -> bool:
    start, end = _hhmm(settings["start"]), _hhmm(settings["end"])
    now = (now_utc or datetime.now(timezone.utc)).astimezone(IST).time()
    if start < end:
        return start <= now < end
    return now >= start or now < end  # crosses midnight


def transfer_number_now(now_utc: Optional[datetime] = None) -> str:
    """The number to forward an incoming call to right now, or "" if the AI should answer."""
    s = get_settings()
    if not s["enabled"] or not s["transfer_number"] or in_ai_hours(s, now_utc):
        return ""
    return s["transfer_number"]


def status(now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    s = get_settings()
    return {**s, "ai_answering_now": not transfer_number_now(now_utc)}
