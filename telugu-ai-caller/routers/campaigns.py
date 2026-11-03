"""
Campaigns Router - Autonomous Auto-Calling Campaigns

"Real Phone" mode (mode = "phone" or "telephony") runs on the outbound dialer
(voice_agent/dialer.py via routers/dialer.py): real calls through the configured
provider, calling rules, retries. "simulation" keeps the old in-memory demo engine.
Status / pause / resume / stop follow whichever engine the last campaign used.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from services.campaign_service import campaign_service

router = APIRouter(tags=["campaigns"])

PHONE_MODES = {"phone", "telephony"}
_last_engine = {"name": "simulation"}


def _dialer():
    """The real-call dialer, if the real-time voice engine is installed."""
    try:
        from routers import dialer
        return dialer
    except ImportError:
        return None


def _use_dialer() -> bool:
    return _last_engine["name"] == "phone" and _dialer() is not None


@router.post("/api/campaign/start")
async def api_start_campaign(payload: Dict[str, Any]):
    lead_ids = payload.get("lead_ids")  # optional list of ints
    mode = payload.get("mode", "simulation")  # "simulation" or "phone"/"telephony"
    delay = int(payload.get("delay_seconds", 4))

    if mode in PHONE_MODES:
        dialer = _dialer()
        if dialer is None:
            raise HTTPException(status_code=409, detail="Real phone calling needs the real-time voice engine (Python 3.13 + Pipecat).")
        result = dialer.start_calling(payload)
        _last_engine["name"] = "phone"
        return {**result, "message": f"Calling started · {result['queued']} lead(s) queued via {result['provider']}."}

    started = await campaign_service.start_campaign(lead_ids=lead_ids, mode=mode, delay_seconds=delay)
    if not started:
        raise HTTPException(status_code=400, detail="Campaign already running or no leads found.")
    _last_engine["name"] = "simulation"
    return {"success": True, "message": "Auto-calling campaign started."}


@router.get("/api/campaign/status")
async def api_campaign_status():
    if _use_dialer():
        return _dialer().campaign_compatible_status()
    return campaign_service.get_status()


@router.post("/api/campaign/pause")
async def api_pause_campaign():
    if _use_dialer():
        _dialer().call_queue.pause()
    else:
        campaign_service.pause_campaign()
    return {"success": True}


@router.post("/api/campaign/resume")
async def api_resume_campaign():
    if _use_dialer():
        _dialer().call_queue.resume()
    else:
        campaign_service.resume_campaign()
    return {"success": True}


@router.post("/api/campaign/stop")
async def api_stop_campaign():
    if _use_dialer():
        _dialer().call_queue.cancel_waiting()
    else:
        campaign_service.stop_campaign()
    return {"success": True}
