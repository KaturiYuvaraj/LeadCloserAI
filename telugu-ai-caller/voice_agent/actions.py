"""
Actions the AI takes during a live call (its "tools").

The LLM writes a marker such as [CALLBACK: 2026-11-04 17:30] at the end of a reply
(see voice_agent/conclusion.py); the session calls `run_action`, which updates the
CRM right away, so nothing is lost if the line drops a second later:

  CALLBACK       a new dialer job at the agreed IST time (the dialer still applies
                 the calling rules: hours, Do-Not-Call)
  MEETING        lead marked DEMO_BOOKED with the time; booked in Google Calendar
                 when it is configured
  DO_NOT_CALL    number added to the opt-out list; open dialer jobs cancelled
  HUMAN_HANDOFF  lead flagged for a team member to call back
  WRONG_PERSON   noted on the lead (usually followed by a CALLBACK)
  SEND_WHATSAPP  message sent through WhatsApp when configured, otherwise queued
                 on the lead for the team

Every action returns a small dict that is stored with the call for analytics.
"""

import re
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any, Dict, Optional

from loguru import logger

from core.db import SessionLocal
from models import CallJob, Lead, OptOut
from voice_agent.rules import IST, db_time

DEFAULT_CALLBACK_TIME = dtime(11, 0)


def parse_when(arg: str, now_utc: Optional[datetime] = None) -> Optional[datetime]:
    """
    'YYYY-MM-DD HH:MM' (IST, as the prompt asks) → aware UTC datetime.
    Also accepts a bare date (11:00 IST) or a bare time (today, or tomorrow if already past).
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)
    text = (arg or "").strip()
    date_m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    time_m = re.search(r"(\d{1,2}):(\d{2})", text[date_m.end():] if date_m else text)
    try:
        if date_m:
            day = datetime(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)), tzinfo=IST)
        elif time_m:
            day = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return None
        hour, minute = (int(time_m.group(1)), int(time_m.group(2))) if time_m else (
            DEFAULT_CALLBACK_TIME.hour, DEFAULT_CALLBACK_TIME.minute)
        when = day.replace(hour=hour, minute=minute)
    except ValueError:
        return None
    if not date_m and when <= now_ist:
        when += timedelta(days=1)
    return when.astimezone(timezone.utc)


def default_callback_time(now_utc: Optional[datetime] = None) -> datetime:
    """No time given: tomorrow 11:00 IST."""
    now_ist = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    tomorrow = (now_ist + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
    return tomorrow.astimezone(timezone.utc)


def _note(lead: Lead, key: str, value: Any):
    variables = dict(lead.variables or {})
    variables[key] = value
    lead.variables = variables


def schedule_callback(lead_id: int, when_utc: datetime, note: str = "", language: Optional[str] = None) -> Dict[str, Any]:
    """Replace any waiting dialer job for this lead with a callback at `when_utc`."""
    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return {"ok": False, "error": "lead not found"}
        session.query(CallJob).filter(
            CallJob.lead_id == lead_id, CallJob.state.in_(("queued", "scheduled", "retry_scheduled"))
        ).update({"state": "cancelled", "block_reason": "replaced_by_callback"}, synchronize_session=False)
        if not lead.consent_source:
            lead.consent_source = f"callback_requested_on_call {datetime.now(IST):%Y-%m-%d %H:%M} IST"
        session.add(CallJob(
            account_id=lead.account_id, lead_id=lead.id, phone_e164=lead.phone_e164, language=language,
            provider="pending", state="scheduled", priority=1, attempt=0, max_attempts=2,
            next_attempt_at=db_time(session, when_utc), last_disposition="callback_requested",
            last_error=note[:500] if note else None,
        ))
        _note(lead, "next_callback_at", when_utc.astimezone(IST).strftime("%Y-%m-%d %H:%M IST"))
        lead.last_outcome = "follow_up"
        session.commit()
        return {"ok": True, "callback_at": when_utc.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")}
    finally:
        session.close()


def cancel_waiting_callbacks(lead_id: int, reason: str = "replaced_by_meeting") -> int:
    """A booked meeting replaces any callback still waiting (the customer agreed one time, not two)."""
    session = SessionLocal()
    try:
        count = session.query(CallJob).filter(
            CallJob.lead_id == lead_id, CallJob.state.in_(("queued", "scheduled", "retry_scheduled")),
            CallJob.last_disposition == "callback_requested",
        ).update({"state": "cancelled", "block_reason": reason}, synchronize_session=False)
        session.commit()
        return count
    finally:
        session.close()


def mark_do_not_call(lead_id: int, reason: str = "asked on call") -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return {"ok": False, "error": "lead not found"}
        lead.opt_out = True
        lead.last_outcome = "lost"
        exists = session.query(OptOut.id).filter(
            OptOut.account_id == lead.account_id, OptOut.phone_e164 == lead.phone_e164
        ).first()
        if not exists:
            session.add(OptOut(account_id=lead.account_id, phone_e164=lead.phone_e164, reason=reason))
        cancelled = session.query(CallJob).filter(
            CallJob.lead_id == lead_id, CallJob.state.in_(("queued", "scheduled", "retry_scheduled"))
        ).update({"state": "cancelled", "block_reason": "opted_out"}, synchronize_session=False)
        session.commit()
        return {"ok": True, "cancelled_jobs": cancelled}
    finally:
        session.close()


def flag_lead(lead_id: int, key: str, value: Any, status: Optional[str] = None) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return {"ok": False, "error": "lead not found"}
        _note(lead, key, value)
        if status:
            _note(lead, "status", status)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


def queue_whatsapp(lead_id: int, what: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return {"ok": False, "error": "lead not found"}
        pending = list((lead.variables or {}).get("pending_whatsapp") or [])
        pending.append({"what": what or "details", "at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")})
        _note(lead, "pending_whatsapp", pending)
        session.commit()
        return {"ok": True, "queued": True}
    finally:
        session.close()


def _provider(kind: str, name: str):
    try:
        from providers import ProviderType, registry
        provider = registry.get(getattr(ProviderType, kind), name)
        return provider if provider and provider.is_configured() else None
    except Exception:
        return None


async def run_action(tag: str, arg: str, lead: Optional[Dict[str, Any]], language: Optional[str] = None,
                     now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Carry out one action marker. Never raises: a failed action must not break the call."""
    import asyncio

    record: Dict[str, Any] = {"action": tag.lower(), "arg": arg}
    lead_id = (lead or {}).get("id")
    if not lead_id:
        record["result"] = {"ok": False, "error": "no lead on this call"}
        return record
    try:
        if tag == "CALLBACK":
            when = parse_when(arg, now_utc) or default_callback_time(now_utc)
            record["result"] = await asyncio.to_thread(schedule_callback, lead_id, when, arg, language)
        elif tag == "DO_NOT_CALL":
            record["result"] = await asyncio.to_thread(mark_do_not_call, lead_id)
        elif tag == "HUMAN_HANDOFF":
            stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
            record["result"] = await asyncio.to_thread(flag_lead, lead_id, "needs_human", {"at": stamp, "note": arg})
        elif tag == "WRONG_PERSON":
            record["result"] = await asyncio.to_thread(flag_lead, lead_id, "wrong_person_note", arg or "someone else answered")
        elif tag == "MEETING":
            when = parse_when(arg, now_utc)
            label = when.astimezone(IST).strftime("%Y-%m-%d %H:%M IST") if when else (arg or "time to confirm")
            result = await asyncio.to_thread(flag_lead, lead_id, "meeting_at", label, "DEMO_BOOKED")
            result["callbacks_cancelled"] = await asyncio.to_thread(cancel_waiting_callbacks, lead_id)
            calendar = _provider("CALENDAR", "google_calendar")
            if calendar and when:
                booked = await calendar.book_meeting(
                    title="S P Associates — Demo Call",
                    start_time=when.astimezone(IST).replace(tzinfo=None).isoformat(),
                    duration_minutes=15, customer_email=lead.get("email"), customer_name=lead.get("name"),
                )
                result["calendar"] = {"ok": bool(booked.get("success")), "meet_link": booked.get("meet_link")}
            record["result"] = result
        elif tag == "SEND_WHATSAPP":
            whatsapp = _provider("MESSAGING", "meta_whatsapp")
            if whatsapp and lead.get("phone"):
                text = f"Hello {lead.get('name') or ''}, as discussed on the call: {arg or 'here are the details'}."
                sent = await whatsapp.send_text_message(to_phone=lead["phone"], message=text)
                record["result"] = {"ok": bool(sent.get("success")), "sent": True}
            else:
                record["result"] = await asyncio.to_thread(queue_whatsapp, lead_id, arg)
        else:
            record["result"] = {"ok": False, "error": "unknown action"}
    except Exception as e:
        logger.error(f"Call action {tag} failed for lead {lead_id}: {e}")
        record["result"] = {"ok": False, "error": str(e)}
    logger.info(f"⚙️  Call action {tag} ({arg}) for lead {lead_id}: {record['result']}")
    return record
