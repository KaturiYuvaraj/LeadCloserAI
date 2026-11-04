"""
Calls Router - Call History, Call Records & Analytics
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger

from core.auth import get_request_account_id
from database import get_call_history, get_call_by_id, get_analytics_summary, update_call_recording

router = APIRouter(tags=["calls"])


@router.get("/api/calls")
async def api_get_calls(request: Request):
    account_id = get_request_account_id(request)
    return {"calls": get_call_history(limit=50, account_id=account_id)}


@router.get("/api/calls/{call_id}")
async def api_get_call_details(call_id: int, request: Request):
    account_id = get_request_account_id(request)
    call_record = get_call_by_id(call_id, account_id=account_id)
    if not call_record:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call_record}


RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"
MAX_RECORDING_BYTES = 50 * 1024 * 1024  # 50 MB, roughly 2 hours of Opus audio


@router.post("/api/calls/{call_id}/recording")
async def api_upload_call_recording(call_id: int, request: Request, file: UploadFile = File(...)):
    """
    Store the browser-side call recording (customer + AI mixed, WebM/Opus)
    so the sales team can replay the conversation before closing the deal.
    """
    account_id = get_request_account_id(request)
    if not get_call_by_id(call_id, account_id=account_id):
        raise HTTPException(status_code=404, detail="Call record not found")
    if file.content_type and not file.content_type.startswith(("audio/", "video/webm")):
        raise HTTPException(status_code=400, detail="Only audio recordings are accepted.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Recording is empty.")
    if len(audio_bytes) > MAX_RECORDING_BYTES:
        raise HTTPException(status_code=413, detail="Recording is larger than 50 MB.")

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    (RECORDINGS_DIR / f"call_{call_id}.webm").write_bytes(audio_bytes)

    recording_url = f"/api/calls/{call_id}/recording"
    update_call_recording(call_id, recording_url)
    logger.info(f"Stored recording for call #{call_id} ({len(audio_bytes) // 1024} KB)")
    return {"success": True, "recording_url": recording_url}


@router.get("/api/calls/{call_id}/recording")
async def api_get_call_recording(call_id: int, request: Request):
    account_id = get_request_account_id(request)
    if not get_call_by_id(call_id, account_id=account_id):
        raise HTTPException(status_code=404, detail="Call record not found")
    # Browser calls are recorded in the browser (WebM); phone calls by the voice engine (stereo WAV)
    for suffix, media_type in ((".webm", "audio/webm"), (".wav", "audio/wav")):
        recording_path = RECORDINGS_DIR / f"call_{call_id}{suffix}"
        if recording_path.exists():
            return FileResponse(recording_path, media_type=media_type, filename=recording_path.name)
    raise HTTPException(status_code=404, detail="No recording stored for this call.")


@router.get("/api/analytics/overview")
async def api_get_analytics_overview(request: Request):
    """
    Return executive-level sales metrics, conversion funnel, objections breakdown,
    sentiment distributions, and AI employee leaderboard.
    """
    try:
        account_id = get_request_account_id(request)
        data = get_analytics_summary(account_id=account_id)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Failed to generate analytics overview: {e}")
        return {"success": False, "error": str(e)}
