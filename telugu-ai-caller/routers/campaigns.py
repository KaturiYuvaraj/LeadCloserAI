"""
Campaigns Router - Autonomous Auto-Calling Campaigns
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from services.campaign_service import campaign_service

router = APIRouter(tags=["campaigns"])


@router.post("/api/campaign/start")
async def api_start_campaign(payload: Dict[str, Any]):
    lead_ids = payload.get("lead_ids")  # optional list of ints
    mode = payload.get("mode", "simulation")  # "simulation" or "telephony"
    delay = int(payload.get("delay_seconds", 4))

    started = await campaign_service.start_campaign(lead_ids=lead_ids, mode=mode, delay_seconds=delay)
    if not started:
        raise HTTPException(status_code=400, detail="Campaign already running or no leads found.")
    return {"success": True, "message": "Auto-calling campaign started."}


@router.get("/api/campaign/status")
async def api_campaign_status():
    return campaign_service.get_status()


@router.post("/api/campaign/pause")
async def api_pause_campaign():
    campaign_service.pause_campaign()
    return {"success": True}


@router.post("/api/campaign/resume")
async def api_resume_campaign():
    campaign_service.resume_campaign()
    return {"success": True}


@router.post("/api/campaign/stop")
async def api_stop_campaign():
    campaign_service.stop_campaign()
    return {"success": True}
