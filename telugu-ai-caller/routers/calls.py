"""
Calls Router - Call History, Call Records & Analytics
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from database import get_call_history, get_call_by_id, get_analytics_summary

router = APIRouter(tags=["calls"])


@router.get("/api/calls")
async def api_get_calls():
    return {"calls": get_call_history(limit=50)}


@router.get("/api/calls/{call_id}")
async def api_get_call_details(call_id: int):
    call_record = get_call_by_id(call_id)
    if not call_record:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call_record}


@router.get("/api/analytics/overview")
async def api_get_analytics_overview():
    """
    Return executive-level sales metrics, conversion funnel, objections breakdown,
    sentiment distributions, and AI employee leaderboard.
    """
    try:
        data = get_analytics_summary()
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Failed to generate analytics overview: {e}")
        return {"success": False, "error": str(e)}
