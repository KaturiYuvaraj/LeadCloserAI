"""
Dialer Router - outbound calling (Phase 0).

  POST /api/dialer/campaigns         queue leads for calling (target: new | all | selected | lead_ids)
  POST /api/dialer/call-now/{id}     call one lead now (front of the queue)
  GET  /api/dialer/status            provider, lines, counts by state, live calls, recent events
  GET  /api/dialer/jobs              queue entries (filter by state / lead)
  POST /api/dialer/pause | resume | stop

The campaign window in the CRM uses these through /api/campaign/* when
"Real Phone" mode is chosen (see routers/campaigns.py).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from core.db import SessionLocal
from models import Call, CallJob, Lead
from voice_agent.dialer import call_queue

router = APIRouter(tags=["dialer"])


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
        max_attempts=int(payload.get("max_attempts", 3)),
    )
    return {"success": True, "provider": call_queue.dialer.name, **counts}


@router.post("/api/dialer/campaigns")
async def dialer_start(payload: Dict[str, Any]):
    return start_calling(payload)


@router.post("/api/dialer/call-now/{lead_id}")
async def dialer_call_now(lead_id: int, payload: Optional[Dict[str, Any]] = None):
    payload = payload or {}
    call_queue.start()
    counts = call_queue.enqueue([lead_id], priority=0, consent_confirmed=True,
                                language=payload.get("language"))
    if counts["not_found"]:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return {"success": True, "provider": call_queue.dialer.name, **counts}


@router.get("/api/dialer/status")
async def dialer_status():
    call_queue.start()
    return call_queue.status()


@router.get("/api/dialer/jobs")
async def dialer_jobs(state: Optional[str] = None, lead_id: Optional[int] = None, limit: int = 100):
    session = SessionLocal()
    try:
        query = session.query(CallJob)
        if state:
            query = query.filter(CallJob.state == state)
        if lead_id:
            query = query.filter(CallJob.lead_id == lead_id)
        jobs = query.order_by(CallJob.id.desc()).limit(max(1, min(limit, 500))).all()
        return {"jobs": [{
            "id": j.id, "lead_id": j.lead_id, "phone": j.phone_e164, "state": j.state,
            "attempt": j.attempt, "max_attempts": j.max_attempts, "provider": j.provider,
            "last_disposition": j.last_disposition, "block_reason": j.block_reason,
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
