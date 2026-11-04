"""
Campaigns Router — Real Outbound Campaign Queue (Phase 0).

All campaigns started from the CRM UI or `/api/campaign/start` run through the
restart-safe outbound campaign queue (`voice_agent/dialer.py` via `routers/dialer.py`),
enforcing calling hours (9 AM–9 PM IST), DND/Opt-Out rules, consent checks,
weekly call limits, and automatic retries.
The legacy fake in-memory simulation mode is removed from the campaign flow.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

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
async def api_start_campaign(payload: Dict[str, Any]):
    dialer = _dialer()
    if dialer is not None:
        # Ensure consent is passed through to the queue (default True when launched via API if not explicitly False)
        dial_payload = dict(payload)
        if "consent_confirmed" not in dial_payload:
            dial_payload["consent_confirmed"] = True
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
