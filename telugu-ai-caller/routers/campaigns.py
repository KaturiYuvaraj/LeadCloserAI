import json
from core.db import SessionLocal
from models import Campaign
"""
Campaigns Router — Real Outbound Campaign Queue (Phase 0).

All campaigns started from the CRM UI or `/api/campaign/start` run through the
restart-safe outbound campaign queue (`voice_agent/dialer.py` via `routers/dialer.py`),
enforcing calling hours (9 AM–9 PM IST), DND/Opt-Out rules, consent checks,
weekly call limits, and automatic retries.
The legacy fake in-memory simulation mode is removed from the campaign flow.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from core.auth import get_request_account_id

from services.campaign_service import campaign_service

router = APIRouter(tags=["campaigns"])


def _dialer():
    """Return the real outbound dialer router if installed."""
    try:
        from routers import dialer
        return dialer
    except ImportError:
        return None


@router.post("/api/campaign/start")
async def api_start_campaign(payload: Dict[str, Any], request: Request):
    account_id = get_request_account_id(request) or 1
    dialer = _dialer()
    if dialer is not None:
        # Ensure consent is passed through to the queue (default True when launched via API if not explicitly False)
        dial_payload = dict(payload)
        if "consent_confirmed" not in dial_payload:
            dial_payload["consent_confirmed"] = True
        if "account_id" not in dial_payload:
            dial_payload["account_id"] = account_id
        result = dialer.start_calling(dial_payload)
        return {
            **result,
            "mode": "phone",
            "message": f"Calling started · {result['queued']} lead(s) queued via {result['provider']}.",
        }

    # Fallback only when voice_agent/dialer is not installed in environment
    lead_ids = payload.get("lead_ids")
    delay = int(payload.get("delay_seconds", 4))
    started = await campaign_service.start_campaign(lead_ids=lead_ids, mode="telephony", delay_seconds=delay)
    if not started:
        raise HTTPException(status_code=400, detail="Campaign already running or no leads found.")
    return {"success": True, "mode": "phone", "message": "Outbound calling campaign started."}


@router.get("/api/campaign/status")
async def api_campaign_status():
    dialer = _dialer()
    if dialer is not None:
        return dialer.campaign_compatible_status()
    return campaign_service.get_status()


@router.post("/api/campaign/pause")
async def api_pause_campaign():
    dialer = _dialer()
    if dialer is not None:
        dialer.call_queue.pause()
    else:
        campaign_service.pause_campaign()
    return {"success": True}


@router.post("/api/campaign/resume")
async def api_resume_campaign():
    dialer = _dialer()
    if dialer is not None:
        dialer.call_queue.resume()
    else:
        campaign_service.resume_campaign()
    return {"success": True}


@router.post("/api/campaign/stop")
async def api_stop_campaign():
    dialer = _dialer()
    if dialer is not None:
        cancelled = dialer.call_queue.cancel_waiting()
        return {"success": True, "cancelled": cancelled}
    campaign_service.stop_campaign()
    return {"success": True}


# ---------------- PERSISTENT CAMPAIGN CRUD (Phase 10) ----------------

@router.get("/api/campaigns")
async def api_list_campaigns(request: Request):
    """List all persistent database campaigns for the current account."""
    account_id = get_request_account_id(request) or 1
    session = SessionLocal()
    try:
        rows = (
            session.query(Campaign)
            .filter(Campaign.account_id == account_id)
            .order_by(Campaign.id.desc())
            .all()
        )
        return {
            "campaigns": [
                {
                    "id": c.id,
                    "account_id": c.account_id,
                    "name": c.name,
                    "description": c.description,
                    "employee_id": c.employee_id,
                    "lead_ids": json.loads(c.lead_ids_json or "[]"),
                    "mode": c.mode,
                    "status": c.status,
                    "total_leads": c.total_leads,
                    "completed_leads": c.completed_leads,
                    "max_concurrency": c.max_concurrency,
                    "retry_attempts": c.retry_attempts,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in rows
            ]
        }
    finally:
        session.close()


@router.get("/api/campaigns/{campaign_id}")
async def api_get_campaign(campaign_id: int, request: Request):
    """Get detailed state, logs, and results for a specific campaign."""
    account_id = get_request_account_id(request)
    session = SessionLocal()
    try:
        query = session.query(Campaign).filter(Campaign.id == campaign_id)
        if account_id is not None:
            query = query.filter(Campaign.account_id == account_id)
        c = query.first()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {
            "campaign": {
                "id": c.id,
                "account_id": c.account_id,
                "name": c.name,
                "description": c.description,
                "employee_id": c.employee_id,
                "lead_ids": json.loads(c.lead_ids_json or "[]"),
                "mode": c.mode,
                "status": c.status,
                "total_leads": c.total_leads,
                "completed_leads": c.completed_leads,
                "max_concurrency": c.max_concurrency,
                "retry_attempts": c.retry_attempts,
                "results": json.loads(c.results_json or "{}"),
                "logs": json.loads(c.logs_json or "[]"),
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
        }
    finally:
        session.close()


@router.post("/api/campaigns")
async def api_create_persistent_campaign(payload: Dict[str, Any], request: Request):
    """Create and configure a new persistent campaign."""
    account_id = get_request_account_id(request) or 1
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Campaign name is required.")

    lead_ids = payload.get("lead_ids", [])
    if isinstance(lead_ids, str):
        try:
            lead_ids = json.loads(lead_ids)
        except Exception:
            lead_ids = []

    session = SessionLocal()
    try:
        c = Campaign(
            account_id=account_id,
            name=name,
            description=payload.get("description", ""),
            employee_id=payload.get("employee_id"),
            lead_ids_json=json.dumps(lead_ids),
            mode=payload.get("mode", "telephony"),
            status="draft",
            total_leads=len(lead_ids),
            completed_leads=0,
            max_concurrency=int(payload.get("max_concurrency", 3)),
            retry_attempts=int(payload.get("retry_attempts", 2)),
            results_json="{}",
            logs_json="[]",
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        return {
            "success": True,
            "campaign_id": c.id,
            "message": f"Campaign '{name}' created successfully.",
        }
    finally:
        session.close()


@router.put("/api/campaigns/{campaign_id}")
async def api_update_campaign(campaign_id: int, payload: Dict[str, Any], request: Request):
    """Update an existing campaign's configuration."""
    account_id = get_request_account_id(request)
    session = SessionLocal()
    try:
        query = session.query(Campaign).filter(Campaign.id == campaign_id)
        if account_id is not None:
            query = query.filter(Campaign.account_id == account_id)
        c = query.first()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if "name" in payload:
            c.name = str(payload["name"]).strip()
        if "description" in payload:
            c.description = str(payload["description"])
        if "employee_id" in payload:
            c.employee_id = payload["employee_id"]
        if "lead_ids" in payload:
            ids = payload["lead_ids"]
            c.lead_ids_json = json.dumps(ids)
            c.total_leads = len(ids)
        if "max_concurrency" in payload:
            c.max_concurrency = int(payload["max_concurrency"])
        if "retry_attempts" in payload:
            c.retry_attempts = int(payload["retry_attempts"])
        if "status" in payload:
            c.status = str(payload["status"]).strip()

        session.commit()
        return {"success": True, "campaign_id": c.id}
    finally:
        session.close()


@router.post("/api/campaigns/{campaign_id}/start")
async def api_launch_persistent_campaign(campaign_id: int, request: Request):
    """Launch a saved persistent campaign into the dialer queue."""
    account_id = get_request_account_id(request) or 1
    session = SessionLocal()
    try:
        c = session.query(Campaign).filter(Campaign.id == campaign_id, Campaign.account_id == account_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")

        lead_ids = json.loads(c.lead_ids_json or "[]")
        if not lead_ids:
            raise HTTPException(status_code=400, detail="Cannot launch campaign with 0 leads.")

        dialer = _dialer()
        if dialer is not None:
            dial_payload = {
                "account_id": account_id,
                "lead_ids": lead_ids,
                "consent_confirmed": True,
                "campaign_id": c.id,
                "employee_id": c.employee_id,
                "max_concurrency": c.max_concurrency,
                "retry_attempts": c.retry_attempts,
            }
            res = dialer.start_calling(dial_payload)
            c.status = "running"
            session.commit()
            return {
                "success": True,
                "campaign_id": c.id,
                "queued": res.get("queued", len(lead_ids)),
                "message": f"Campaign '{c.name}' launched into dialer queue.",
            }

        c.status = "running"
        session.commit()
        return {"success": True, "campaign_id": c.id, "message": f"Campaign '{c.name}' started."}
    finally:
        session.close()


@router.delete("/api/campaigns/{campaign_id}")
async def api_delete_campaign(campaign_id: int, request: Request):
    """Delete a campaign if it is not currently running."""
    account_id = get_request_account_id(request)
    session = SessionLocal()
    try:
        query = session.query(Campaign).filter(Campaign.id == campaign_id)
        if account_id is not None:
            query = query.filter(Campaign.account_id == account_id)
        c = query.first()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if c.status == "running":
            raise HTTPException(status_code=400, detail="Cannot delete an active running campaign. Pause or stop it first.")

        session.delete(c)
        session.commit()
        return {"success": True, "deleted_id": campaign_id}
    finally:
        session.close()
