"""
Dialer Router - outbound calling (Phase 0).

  POST /api/dialer/campaigns         queue leads for calling (target: new | all | selected | lead_ids)
  POST /api/dialer/call-now/{id}     call one lead now (front of the queue)
  POST /api/dialer/lead-for-number   find or add the lead for a typed number ("Call a number")
  GET|POST /api/dialer/engine        which engine places calls: ours (Shreya) or Sarvam's agent (Shriya)
  GET  /api/dialer/status            provider, lines, counts by state, live calls, recent events
  GET  /api/dialer/jobs              queue entries (filter by state / lead)
  POST /api/dialer/pause | resume | stop

The campaign window in the CRM uses these through /api/campaign/* when
"Real Phone" mode is chosen (see routers/campaigns.py).
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from core.auth import get_current_user, get_optional_user, get_request_account_id
from core.db import SessionLocal
from database import clean_phone, create_lead
from models import Call, CallJob, Lead
from voice_agent import credits, samvaad
from voice_agent.dialer import call_queue
from voice_agent.rules import is_dialable_number

def _login_when_required(request: Request) -> None:
    """With AUTH_STRICT=true every dialer route needs a signed-in user (401 otherwise)."""
    get_optional_user(request)


router = APIRouter(tags=["dialer"], dependencies=[Depends(_login_when_required)])


def resolve_targets(target: str = "new", lead_ids: Optional[List[int]] = None,
                    lead_id: Optional[int] = None) -> List[int]:
    """new = leads never called · all = every lead · selected = one lead · or an explicit list."""
    if lead_ids:
        return [int(i) for i in lead_ids]
    if target == "selected":
        return [int(lead_id)] if lead_id else []
    session = SessionLocal()
    try:
        query = session.query(Lead.id).filter(Lead.opt_out.is_(False))
        if target != "all":
            called = session.query(Call.lead_id).filter(Call.lead_id.isnot(None)).distinct()
            query = query.filter(~Lead.id.in_(called))
        return [row.id for row in query.order_by(Lead.id).all()]
    finally:
        session.close()


def start_calling(payload: Dict[str, Any]) -> Dict[str, Any]:
    targets = resolve_targets(payload.get("target", "new"), payload.get("lead_ids"), payload.get("lead_id"))
    if not targets:
        raise HTTPException(status_code=400, detail="No leads to call for this selection.")
    max_lines = payload.get("max_lines")
    if max_lines:
        call_queue.max_lines = max(1, min(int(max_lines), 50))
    call_queue.paused = False
    call_queue.start()
    counts = call_queue.enqueue(
        targets,
        consent_confirmed=bool(payload.get("consent_confirmed")),
        language=payload.get("language"),
        priority=int(payload.get("priority", 5)),
        max_attempts=int(payload["max_attempts"]) if payload.get("max_attempts") else None,
    )
    return {"success": True, "provider": call_queue.dialer.name, **counts}


@router.post("/api/dialer/campaigns")
async def dialer_start(payload: Dict[str, Any]):
    return start_calling(payload)


REASONS = {
    "account_not_approved": "Calling is not approved for this account yet.",
    "opted_out": "This person asked never to be called (Do-Not-Call).",
    "invalid_number": "The phone number is not valid.",
    "no_consent": "There is no record that this person agreed to be called.",
    "weekly_limit": "This lead already reached the weekly call limit.",
    "low_credit": "The account does not have enough call credit.",
}


def _lead_of_user(lead_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    """The lead, if it belongs to the signed-in user's company (404 otherwise: never reveal other companies' leads)."""
    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if lead is None or lead.account_id != user.get("account_id"):
            raise HTTPException(status_code=404, detail="Lead not found.")
        return {"id": lead.id, "name": lead.name, "phone": lead.phone_e164}
    finally:
        session.close()


def evaluate_manual_call(lead_id: int, user: Dict[str, Any], consent_confirmed: bool = False) -> Dict[str, Any]:
    """
    Can this person press "Call now" on this lead? Shared by the preflight check (so the button can show
    the right warning) and by the call itself (the server never trusts what the page checked).
    """
    lead = _lead_of_user(lead_id, user)
    engine = samvaad.current_engine()
    out: Dict[str, Any] = {"lead": lead, "provider": call_queue.dialer.name, "engine": engine,
                           "engine_label": samvaad.ENGINES[engine],
                           "simulated": engine == "pipecat" and call_queue.dialer.name == "fake"}
    block = credits.blocked()
    if block:
        return {**out, "can_call": False, "status": "service_unavailable", "message": block["message"]}
    if call_queue.paused:
        return {**out, "can_call": False, "status": "paused", "message": "Calling is paused. Press Resume first."}
    preview = call_queue.preview_call(lead_id, consent_confirmed)
    out["last_called_hours_ago"] = preview.get("last_called_hours_ago")
    out["outside_calling_hours"] = bool(preview.get("outside_calling_hours"))
    out["calls_this_week"] = preview.get("calls_this_week", 0)
    reason = preview.get("reason")
    if preview["status"] == "blocked":
        return {**out, "can_call": False, "status": "blocked", "reason": reason,
                "message": REASONS.get(reason, "Calling this lead is blocked."), "needs_consent": reason == "no_consent"}
    if preview["status"] == "deferred":
        return {**out, "can_call": False, "status": "deferred", "reason": reason, "can_schedule": True,
                "message": REASONS.get(reason, "This lead cannot be called right now."),
                "next_allowed_at": preview.get("next_allowed_at")}
    return {**out, "can_call": True, "status": "allowed"}


async def start_manual_call(lead_id: int, user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Press "Call now": check the rules, then put the lead at the front of the dialer queue."""
    consent = bool(payload.get("consent_confirmed"))
    verdict = await asyncio.to_thread(evaluate_manual_call, lead_id, user, consent)
    if not verdict["can_call"] and not (verdict["status"] == "deferred" and payload.get("schedule")):
        return {"success": False, **verdict}
    call_queue.start()
    counts = await asyncio.to_thread(
        lambda: call_queue.enqueue([lead_id], priority=0, consent_confirmed=consent,
                                   language=payload.get("language"), consent_by=user.get("email")))
    job_id = await asyncio.to_thread(call_queue.open_job_id, lead_id)
    if counts["queued"]:
        status = "scheduled" if verdict["status"] == "deferred" else "queued"
    else:
        status = "in_progress"  # the lead is on the phone right now
    logger.info(f"📞 Call now by {user.get('email')} · lead {lead_id} · {status}"
                + (f" · consent confirmed by them" if consent else ""))
    return {"success": True, "provider": call_queue.dialer.name, "status": status, "job_id": job_id, **counts,
            **{k: verdict[k] for k in ("lead", "simulated", "outside_calling_hours", "last_called_hours_ago") if k in verdict}}


def lead_for_number(user: Dict[str, Any], phone: str, name: str, language: Optional[str]) -> Dict[str, Any]:
    """The signed-in company's lead with this number, created if it's new."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    number = clean_phone(phone) if digits else ""
    if not is_dialable_number(number) or not digits.strip("0"):
        raise HTTPException(status_code=400, detail="Please enter a valid phone number, for example 9876543210.")
    account_id = user.get("account_id")
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.account_id == account_id, Lead.phone_e164 == number).first()
        if lead:
            return {"id": lead.id, "name": lead.name, "phone": lead.phone_e164, "created": False}
    finally:
        session.close()
    label = (name or "").strip() or f"Manual call {number[-10:]}"
    lead_id = create_lead({"name": label, "phone": number, "source": "manual", "preferred_language": language or "te-IN"},
                          account_id=account_id)
    return {"id": lead_id, "name": label, "phone": number, "created": True}


@router.post("/api/dialer/lead-for-number")
async def dialer_lead_for_number(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    """Dashboard "Call a number": find or add the lead; the page then runs the normal Call now flow."""
    return await asyncio.to_thread(lead_for_number, user, payload.get("phone"), payload.get("name"), payload.get("language"))


@router.get("/api/dialer/call-now/{lead_id}/check")
async def dialer_call_now_check(lead_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    """What would happen if "Call now" were pressed (nothing is saved or dialled)."""
    return await asyncio.to_thread(evaluate_manual_call, lead_id, user)


@router.post("/api/dialer/call-now/{lead_id}")
async def dialer_call_now(lead_id: int, payload: Optional[Dict[str, Any]] = None,
                          user: Dict[str, Any] = Depends(get_current_user)):
    return await start_manual_call(lead_id, user, payload or {})


@router.get("/api/dialer/engine")
async def dialer_engine(user: Dict[str, Any] = Depends(get_current_user)):
    """Which engine places the next calls: our engine, or Sarvam's own agent."""
    return samvaad.engine_options()


@router.post("/api/dialer/engine")
async def dialer_set_engine(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    try:
        samvaad.set_engine(str(payload.get("engine") or ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"Calling engine set to {samvaad.current_engine()} by {user.get('email') or user.get('id')}")
    return samvaad.engine_options()


@router.get("/api/dialer/status")
async def dialer_status():
    call_queue.start()
    return call_queue.status()


@router.get("/api/dialer/jobs")
async def dialer_jobs(request: Request, state: Optional[str] = None, lead_id: Optional[int] = None, limit: int = 100):
    account_id = get_request_account_id(request)
    session = SessionLocal()
    try:
        query = session.query(CallJob)
        if account_id is not None:
            query = query.filter(CallJob.account_id == account_id)
        if state:
            query = query.filter(CallJob.state == state)
        if lead_id:
            query = query.filter(CallJob.lead_id == lead_id)
        jobs = query.order_by(CallJob.id.desc()).limit(max(1, min(limit, 500))).all()
        return {"jobs": [{
            "id": j.id, "lead_id": j.lead_id, "phone": j.phone_e164, "state": j.state,
            "attempt": j.attempt, "max_attempts": j.max_attempts, "provider": j.provider,
            "last_disposition": j.last_disposition, "block_reason": j.block_reason, "last_error": j.last_error,
            "next_attempt_at": j.next_attempt_at.isoformat() if j.next_attempt_at else None,
            "call_id": j.call_id,
        } for j in jobs]}
    finally:
        session.close()


@router.post("/api/dialer/pause")
async def dialer_pause():
    call_queue.pause()
    return {"success": True}


@router.post("/api/dialer/resume")
async def dialer_resume():
    call_queue.resume()
    return {"success": True}


@router.post("/api/dialer/stop")
async def dialer_stop():
    cancelled = call_queue.cancel_waiting()
    return {"success": True, "cancelled": cancelled}


def campaign_compatible_status() -> Dict[str, Any]:
    """The dialer status in the shape the CRM campaign banner already reads."""
    status = call_queue.status()
    counts = status["counts"]
    outcomes = status.get("outcomes", {})
    total = status["total"]
    finished = status["finished"]
    current = status["active_calls"][0] if status["active_calls"] else None
    return {
        "is_running": bool(total and finished < total),
        "is_paused": status["paused"],
        "total_leads": total,
        "completed_leads": finished,
        "progress_percent": int(finished * 100 / total) if total else 0,
        "current_lead": {"name": current["name"], "phone": current["phone"]} if current else None,
        "results": {
            "demo_scheduled": outcomes.get("demo_scheduled", 0) + outcomes.get("meeting_booked", 0),
            "closed_won": outcomes.get("closed_won", 0),
            "follow_up": (outcomes.get("follow_up", 0) + outcomes.get("qualifying", 0)
                          + outcomes.get("qualified", 0) + counts.get("retry_scheduled", 0)
                          + counts.get("scheduled", 0)),
            "lost": outcomes.get("lost", 0) + counts.get("not_reachable", 0),
            "failed": counts.get("blocked", 0),
        },
        "logs": status["events"],
        "mode": "phone",
        "dialer": status,
    }
