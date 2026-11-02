"""
Voice Router - real-time browser calls on the Pipecat engine.

Flow:
  1. POST /api/voice/offer        browser sends its WebRTC offer (+ lead, language, reply wait)
                                  → server starts a WebCallSession, returns the SDP answer + session id
  2. live audio both ways over WebRTC; transcripts / speaking / latency events on the data channel
  3. POST /api/voice/sessions/{id}/hangup    end the call
  4. GET  /api/voice/sessions/{id}/summary   waits for the post-call summary and saved call id

GET /api/voice/config.js tells the dashboard which engine to use (VOICE_ENGINE env:
"pipecat" default, or "classic" to fall back to the /ws/web-call engine).
"""

import asyncio
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel

from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from voice_agent.session import WebCallSession

router = APIRouter(tags=["voice"])

VOICE_ENGINE = os.getenv("VOICE_ENGINE", "pipecat").strip().lower()
ICE_SERVERS = [IceServer(urls=url.strip()) for url in os.getenv(
    "VOICE_ICE_SERVERS", "stun:stun.l.google.com:19302").split(",") if url.strip()]

_webrtc_handler = SmallWebRTCRequestHandler(ice_servers=ICE_SERVERS)
_sessions: Dict[str, WebCallSession] = {}
_session_created: Dict[str, float] = {}
_session_tasks: Dict[str, asyncio.Task] = {}
SESSION_TTL_SECONDS = 2 * 60 * 60


class VoiceOffer(BaseModel):
    sdp: str
    type: str
    pc_id: Optional[str] = None
    restart_pc: Optional[bool] = None
    lead_id: Optional[int] = None
    lang: Optional[str] = None
    wait_ms: Optional[int] = None


class IceCandidateIn(BaseModel):
    candidate: str
    sdp_mid: str
    sdp_mline_index: int


class IcePatch(BaseModel):
    pc_id: str
    candidates: list[IceCandidateIn]


def _prune_sessions():
    cutoff = time.time() - SESSION_TTL_SECONDS
    for sid in [s for s, created in _session_created.items() if created < cutoff]:
        _sessions.pop(sid, None)
        _session_created.pop(sid, None)


def _get_session(session_id: str) -> WebCallSession:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")
    return session


@router.get("/api/voice/config.js")
async def voice_engine_config():
    engine = "pipecat" if VOICE_ENGINE == "pipecat" else "classic"
    return Response(content=f'window.LC_VOICE_ENGINE = "{engine}";\n', media_type="application/javascript")


@router.post("/api/voice/offer")
async def voice_offer(offer: VoiceOffer):
    if VOICE_ENGINE != "pipecat":
        raise HTTPException(status_code=409, detail="Real-time voice engine is disabled (VOICE_ENGINE=classic).")

    _prune_sessions()
    created: Dict[str, Any] = {}

    async def on_connection(connection: SmallWebRTCConnection):
        session = WebCallSession(connection, lead_id=offer.lead_id, language=offer.lang, wait_ms=offer.wait_ms)
        _sessions[session.session_id] = session
        _session_created[session.session_id] = time.time()
        created["session"] = session
        task = asyncio.create_task(session.run())
        _session_tasks[session.session_id] = task
        task.add_done_callback(lambda _t, sid=session.session_id: _session_tasks.pop(sid, None))

    try:
        answer = await asyncio.wait_for(
            _webrtc_handler.handle_web_request(
                request=SmallWebRTCRequest(
                    sdp=offer.sdp, type=offer.type, pc_id=offer.pc_id, restart_pc=offer.restart_pc,
                ),
                webrtc_connection_callback=on_connection,
            ),
            timeout=20,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="WebRTC offer could not be processed (timed out).")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid WebRTC offer: {e}")
    session = created.get("session")
    if not answer or not session:
        raise HTTPException(status_code=500, detail="Could not start the voice session.")
    logger.info(f"Voice session {session.session_id} created for lead {offer.lead_id}")
    return {**answer, "session_id": session.session_id, "language": session.language}


@router.patch("/api/voice/offer")
async def voice_ice_candidates(patch: IcePatch):
    await _webrtc_handler.handle_patch_request(
        SmallWebRTCPatchRequest(
            pc_id=patch.pc_id,
            candidates=[IceCandidate(c.candidate, c.sdp_mid, c.sdp_mline_index) for c in patch.candidates],
        )
    )
    return {"success": True}


@router.post("/api/voice/sessions/{session_id}/text")
async def voice_text_input(session_id: str, payload: Dict[str, Any]):
    await _get_session(session_id).handle_text_input(str(payload.get("text", "")))
    return {"success": True}


@router.post("/api/voice/sessions/{session_id}/hangup")
async def voice_hangup(session_id: str):
    await _get_session(session_id).hangup()
    return {"success": True}


@router.get("/api/voice/sessions/{session_id}/summary")
async def voice_summary(session_id: str, wait_seconds: int = 25):
    session = _get_session(session_id)
    try:
        await asyncio.wait_for(session.done.wait(), timeout=max(1, min(wait_seconds, 60)))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=202, detail="Summary not ready yet.")
    return session.result
