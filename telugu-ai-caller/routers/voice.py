"""
Voice Router - real-time browser calls on the Pipecat engine.

Browser flow:
  1. POST /api/voice/offer        browser sends its WebRTC offer (+ lead, language, reply wait)
                                  → server starts a WebCallSession, returns the SDP answer + session id
  2. live audio both ways over WebRTC; transcripts / speaking / latency events on the data channel
  3. POST /api/voice/sessions/{id}/hangup    end the call
  4. GET  /api/voice/sessions/{id}/summary   waits for the post-call summary and saved call id

Phone flow (Exotel):
  Exotel Voicebot applet → wss://<host>/api/voice/exotel/stream[?lead_id=..&lang=..]
  The Exotel handshake (connected/start) is parsed, then a PhoneCallSession runs the
  same conversation core over 8 kHz PCM and saves the call when Exotel hangs up.

Phone flow (Vobiz, also numbers rented from Sarvam):
  Vobiz application Answer URL → POST https://<host>/api/voice/vobiz/answer[?lead_id=..&lang=..]
  We return <Stream> XML pointing at wss://<host>/api/voice/vobiz/stream; Vobiz streams
  16 kHz Linear16 audio there and a VobizCallSession runs the same conversation core.
  Hangup URL → POST https://<host>/api/voice/vobiz/hangup

GET /api/voice/config.js tells the dashboard which engine to use (VOICE_ENGINE env:
"pipecat" default, or "classic" to fall back to the /ws/web-call engine).
"""

import asyncio
import os
import time
from typing import Any, Dict, Optional

import json
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, WebSocket
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

from pipecat.runner.utils import parse_telephony_websocket

from voice_agent.session import BaseCallSession, PhoneCallSession, VobizCallSession, WebCallSession
from voice_agent.dialer import call_queue
from voice_agent import webhook_auth
from voice_agent.vobiz import build_answer_xml, parse_start_message

router = APIRouter(tags=["voice"])

VOICE_ENGINE = os.getenv("VOICE_ENGINE", "pipecat").strip().lower()
ICE_SERVERS = [IceServer(urls=url.strip()) for url in os.getenv(
    "VOICE_ICE_SERVERS", "stun:stun.l.google.com:19302").split(",") if url.strip()]

_webrtc_handler = SmallWebRTCRequestHandler(ice_servers=ICE_SERVERS)
_sessions: Dict[str, BaseCallSession] = {}
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
    employee_id: Optional[int] = None  # AI employee to use; default: the live one


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


def _get_session(session_id: str) -> BaseCallSession:
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
        session = WebCallSession(connection, lead_id=offer.lead_id, language=offer.lang, wait_ms=offer.wait_ms,
                                 employee_id=offer.employee_id)
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


@router.api_route("/api/voice/exotel/status", methods=["GET", "POST"])
async def exotel_voice_status(request: Request):
    """Exotel StatusCallback for calls placed by the dialer (terminal events)."""
    params = dict(request.query_params)
    try:
        body = await request.json()
        if isinstance(body, dict):
            params.update({k: str(v) for k, v in body.items() if not isinstance(v, (dict, list))})
    except Exception:
        try:
            form = await request.form()
            params.update({k: str(v) for k, v in form.items()})
        except Exception:
            pass
    status = params.get("Status") or params.get("CallStatus") or ""
    duration = params.get("ConversationDuration") or params.get("Duration") or "0"
    logger.info(f"Exotel status · call {params.get('CallSid')} · {status} · {duration}s · job {params.get('job_id')}")
    job_id = params.get("job_id", "")
    if job_id.isdigit():
        try:
            seconds = int(float(duration))
        except ValueError:
            seconds = 0
        await asyncio.to_thread(call_queue.on_provider_hangup, int(job_id), status, seconds, "")
    return {"success": True}


@router.websocket("/api/voice/exotel/stream")
async def exotel_voice_stream(websocket: WebSocket):
    """Exotel Voicebot applet stream: one phone call on the real-time engine."""
    await websocket.accept()
    try:
        transport_type, call_data = await asyncio.wait_for(parse_telephony_websocket(websocket), timeout=10)
    except Exception as e:
        logger.warning(f"Exotel stream rejected: could not read the call handshake ({e})")
        await websocket.close(code=1008)
        return

    if transport_type != "exotel":
        logger.warning(f"Exotel stream rejected: unexpected transport '{transport_type}'")
        await websocket.close(code=1008)
        return

    _prune_sessions()
    session = PhoneCallSession(websocket, call_data, dict(websocket.query_params))
    _sessions[session.session_id] = session
    _session_created[session.session_id] = time.time()
    if session.job_id:
        await asyncio.to_thread(call_queue.on_answered, session.job_id)
    logger.info(
        f"Phone call {session.session_id} · Exotel call {session.call_sid} · "
        f"{session.direction} · from {session.caller} to {session.callee} · lead {session.lead_id}"
    )
    await session.run()


# ---------------------------------------------------------------------------- Vobiz

def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0

def _public_ws_base(request: Request) -> str:
    """wss://host for the stream URL, honouring tunnels/proxies (or VOICE_PUBLIC_WS_BASE)."""
    override = os.getenv("VOICE_PUBLIC_WS_BASE", "").strip().rstrip("/")
    if override:
        return override
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{'wss' if proto == 'https' else 'ws'}://{host}"


async def _request_params(request: Request) -> Dict[str, str]:
    params = {k: v for k, v in request.query_params.items()}
    if request.method == "POST":
        try:
            form = await request.form()
            params.update({k: str(v) for k, v in form.items()})
        except Exception:
            pass
    return params


@router.api_route("/api/voice/vobiz/answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request):
    """Vobiz Answer URL: tell Vobiz to stream this call to the real-time engine."""
    params = await _request_params(request)
    if not webhook_auth.allowed(params):
        logger.warning(f"Vobiz answer rejected: wrong or missing key (from {request.client.host if request.client else '?'})")
        return Response(status_code=403, content="forbidden")
    stream_query = {
        key: value for key, value in {
            "lead_id": params.get("lead_id", ""),
            "lang": params.get("lang", ""),
            "from": params.get("From", params.get("from", "")),
            "to": params.get("To", params.get("to", "")),
            "call_id": params.get("CallUUID", params.get("call_id", "")),
            "job_id": params.get("job_id", ""),
            "key": params.get("key", ""),
        }.items() if value
    }
    if stream_query.get("job_id", "").isdigit():
        await asyncio.to_thread(call_queue.on_answered, int(stream_query["job_id"]))
    stream_url = f"{_public_ws_base(request)}/api/voice/vobiz/stream"
    if stream_query:
        stream_url += "?" + urlencode(stream_query)
    logger.info(f"Vobiz answer · call {stream_query.get('call_id')} · from {stream_query.get('from')} "
                f"to {stream_query.get('to')} · lead {stream_query.get('lead_id')}")
    return Response(content=build_answer_xml(stream_url), media_type="application/xml")


@router.api_route("/api/voice/vobiz/hangup", methods=["GET", "POST"])
async def vobiz_hangup(request: Request):
    params = await _request_params(request)
    if not webhook_auth.allowed(params):
        logger.warning(f"Vobiz hangup rejected: wrong or missing key (from {request.client.host if request.client else '?'})")
        return Response(status_code=403, content="forbidden")
    logger.info(f"Vobiz hangup · call {params.get('CallUUID')} · status {params.get('CallStatus')} · "
                f"duration {params.get('Duration')}s · cause {params.get('HangupCause')}")
    job_id = params.get("job_id", "")
    if job_id.isdigit():
        await asyncio.to_thread(
            call_queue.on_provider_hangup, int(job_id), params.get("CallStatus", ""),
            _to_int(params.get("Duration")), params.get("HangupCause", ""),
        )
    return {"success": True}


@router.websocket("/api/voice/vobiz/stream")
async def vobiz_voice_stream(websocket: WebSocket):
    """Vobiz bidirectional stream: one phone call on the real-time engine."""
    await websocket.accept()
    query = dict(websocket.query_params)
    if not webhook_auth.allowed(query):
        logger.warning("Vobiz stream rejected: wrong or missing key")
        await websocket.close(code=1008)
        return

    async def wait_for_start():
        while True:
            raw = await websocket.receive_text()
            logger.info(f"Vobiz stream event received: {raw[:120]}")
            message = json.loads(raw)
            if message.get("event") == "start":
                return message

    try:
        start_message = await asyncio.wait_for(wait_for_start(), timeout=10)
    except Exception as e:
        logger.warning(f"Vobiz stream rejected: no start event ({e})")
        await websocket.close(code=1008)
        return

    call_data = parse_start_message(start_message)
    call_data["from"] = call_data.get("from") or query.get("from", "")
    call_data["to"] = call_data.get("to") or query.get("to", "")
    call_data["call_id"] = call_data.get("call_id") or query.get("call_id", "")
    if not call_data.get("stream_id"):
        logger.warning("Vobiz stream rejected: start event has no streamId")
        await websocket.close(code=1008)
        return

    _prune_sessions()
    session = VobizCallSession(websocket, call_data, query)
    _sessions[session.session_id] = session
    _session_created[session.session_id] = time.time()
    logger.info(
        f"Phone call {session.session_id} · Vobiz call {session.call_sid} · {session.direction} · "
        f"from {session.caller} to {session.callee} · lead {session.lead_id} · "
        f"audio {session.inbound_encoding}@{session.inbound_sample_rate}"
    )
    await session.run()
