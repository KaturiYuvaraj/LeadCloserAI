"""
Main Application Entrypoint for Telugu AI Caller & Lead Closing CRM.
FastAPI Web Server with WebSockets for interactive voice calling,
Twilio Media Streams for telephony, and REST APIs for Lead Management.
"""

import os
import json
import base64
import time
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from config import CORS_ORIGINS, HOST, PORT, DEFAULT_TTS_SPEAKER, DEFAULT_TTS_MODEL, DEFAULT_STT_MODEL
from database import (
    init_db,
    get_all_leads,
    get_lead_by_id,
    create_lead,
    batch_create_leads,
    update_lead,
    delete_lead,
    save_call_record,
    get_call_history,
    get_call_by_id,
    get_calls_for_lead,
    get_company_profile,
    update_company_profile
)
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from services.audio_processor import pcm_to_wav, mulaw_to_wav, wav_to_mulaw
from services.telephony_service import telephony_service
from services.excel_service import parse_excel_or_csv, generate_sample_excel_template, generate_leads_export_excel
from services.campaign_service import campaign_service
from services.language_utils import detect_language

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Telugu AI Caller & Lead Closer",
    description="Natural language Telugu AI calling agent to qualify and close software leads.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "templates").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("Database initialized. Telugu AI Caller ready.")


# =====================================================================
# HTML FRONTEND ROUTE
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    profile = get_company_profile()
    leads = get_all_leads()
    calls = get_call_history(limit=20)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "profile": profile,
        "leads": leads,
        "calls": calls
    })


# =====================================================================
# EXCEL / CSV LEADS INGESTION & TEMPLATE (MUST PRECEDE PARAMETRIZED ROUTES)
# =====================================================================

@app.get("/api/leads/template")
async def api_download_template():
    """
    Download a formatted Excel template for easy lead upload.
    """
    excel_bytes = generate_sample_excel_template()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_template.xlsx"}
    )


@app.get("/api/leads/export-excel")
async def api_export_leads_excel():
    """
    Download all leads with their AI conversation summaries, deal stages,
    sentiments, objections, and action items in an Excel report.
    """
    leads = get_all_leads()
    excel_bytes = generate_leads_export_excel(leads)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_with_call_summaries.xlsx"}
    )


@app.post("/api/leads/upload-excel")
async def api_upload_excel_leads(file: UploadFile = File(...)):
    """
    Upload Excel (.xlsx) or CSV file with lead details.
    Parses customer name, phone, service needed, budget, notes, etc.
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .csv files are supported.")

    file_bytes = await file.read()
    leads, errors = parse_excel_or_csv(file_bytes, file.filename)

    if not leads and errors:
        return JSONResponse(status_code=400, content={"success": False, "errors": errors})

    inserted, updated = batch_create_leads(leads)
    logger.info(f"Ingested {len(leads)} leads from {file.filename}: {inserted} inserted, {updated} updated.")

    return {
        "success": True,
        "total_parsed": len(leads),
        "inserted": inserted,
        "updated": updated,
        "errors": errors
    }


# =====================================================================
# REST APIS FOR CRM & LEADS
# =====================================================================

@app.get("/api/leads")
async def api_get_leads():
    return {"leads": get_all_leads()}


@app.get("/api/leads/{lead_id}")
async def api_get_lead(lead_id: int):
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead": lead}


@app.post("/api/leads")
async def api_create_lead(lead_data: Dict[str, Any]):
    lead_id = create_lead(lead_data)
    return {"success": True, "lead_id": lead_id}


@app.get("/api/calls/{call_id}")
async def api_get_call_details(call_id: int):
    call_record = get_call_by_id(call_id)
    if not call_record:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call_record}


@app.get("/api/leads/{lead_id}/calls")
async def api_get_lead_calls(lead_id: int):
    return {"calls": get_calls_for_lead(lead_id)}


# =====================================================================
# AUTONOMOUS AUTO-CALLING CAMPAIGN APIS
# =====================================================================

@app.post("/api/campaign/start")
async def api_start_campaign(payload: Dict[str, Any]):
    lead_ids = payload.get("lead_ids")  # optional list of ints
    mode = payload.get("mode", "simulation")  # "simulation" or "telephony"
    delay = int(payload.get("delay_seconds", 4))

    started = await campaign_service.start_campaign(lead_ids=lead_ids, mode=mode, delay_seconds=delay)
    if not started:
        raise HTTPException(status_code=400, detail="Campaign already running or no leads found.")
    return {"success": True, "message": "Auto-calling campaign started."}


@app.get("/api/campaign/status")
async def api_campaign_status():
    return campaign_service.get_status()


@app.post("/api/campaign/pause")
async def api_pause_campaign():
    campaign_service.pause_campaign()
    return {"success": True}


@app.post("/api/campaign/resume")
async def api_resume_campaign():
    campaign_service.resume_campaign()
    return {"success": True}


@app.post("/api/campaign/stop")
async def api_stop_campaign():
    campaign_service.stop_campaign()
    return {"success": True}


@app.put("/api/leads/{lead_id}")
async def api_update_lead(lead_id: int, updates: Dict[str, Any]):
    ok = update_lead(lead_id, updates)
    return {"success": ok}


@app.delete("/api/leads/{lead_id}")
async def api_delete_lead(lead_id: int):
    ok = delete_lead(lead_id)
    return {"success": ok}


@app.get("/api/calls")
async def api_get_calls():
    return {"calls": get_call_history(limit=50)}


@app.get("/api/profile")
async def api_get_profile():
    return {"profile": get_company_profile()}


@app.post("/api/profile")
async def api_update_profile(data: Dict[str, Any]):
    ok = update_company_profile(data)
    return {"success": ok}


# =====================================================================
# VOICE TEST & TELEPHONY APIS
# =====================================================================

@app.post("/api/tts/test")
async def api_test_tts(payload: Dict[str, Any]):
    text = payload.get("text", "నమస్కారం! మేము మీ వ్యాపారం కోసం అధునాతన సాఫ్ట్‌వేర్ మరియు AI సేవలను అందిస్తున్నాము.")
    speaker = payload.get("speaker", DEFAULT_TTS_SPEAKER)
    model = payload.get("model", DEFAULT_TTS_MODEL)
    language_code = payload.get("language_code")

    try:
        audio_bytes = await sarvam_client.text_to_speech(
            text=text,
            language_code=language_code,
            speaker=speaker,
            model=model
        )
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        logger.error(f"TTS Test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/call/outbound")
async def api_outbound_call(payload: Dict[str, Any], request: Request):
    to_phone = payload.get("phone")
    lead_id = payload.get("lead_id")
    if not to_phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    result = await telephony_service.initiate_outbound_call(
        to_phone=to_phone,
        lead_id=lead_id,
        webhook_host=request.headers.get("host")
    )
    return result


@app.post("/telephony/twiml")
async def telephony_twiml(request: Request, lead_id: Optional[int] = Query(None)):
    host = request.headers.get("host", "localhost:8000")
    twiml_xml = telephony_service.generate_twiml_stream(host=host, lead_id=lead_id)
    return Response(content=twiml_xml, media_type="application/xml")


# =====================================================================
# INTERACTIVE BROWSER CALL WEBSOCKET (/ws/web-call)
# =====================================================================

@app.websocket("/ws/web-call")
async def websocket_web_call(
    websocket: WebSocket,
    lead_id: Optional[int] = Query(None),
    lang: Optional[str] = Query(None)
):
    """
    Real-time interactive voice call session between the browser user and the AI Sales Closer.
    Supports trilingual conversation in Telugu, Hindi, and English based on the customer.
    """
    await websocket.accept()
    logger.info(f"Interactive Web Call started. Lead ID: {lead_id}, Preferred Lang: {lang}")

    conversation_history: List[Dict[str, str]] = []
    start_time = time.time()
    call_lead = get_lead_by_id(lead_id) if lead_id else None
    active_lang = lang or (call_lead.get("preferred_language") if call_lead else None) or "te-IN"

    # Step 1: Speak initial greeting
    greeting_text = await sales_agent.get_initial_greeting(lead_id, language_code=active_lang)
    conversation_history.append({"role": "assistant", "content": greeting_text})
    greeting_lang = detect_language(greeting_text)

    try:
        greeting_audio = await sarvam_client.text_to_speech(greeting_text, language_code=greeting_lang)
        greeting_audio_b64 = base64.b64encode(greeting_audio).decode("utf-8")

        await websocket.send_json({
            "event": "ai_speech",
            "text": greeting_text,
            "audio": greeting_audio_b64,
            "role": "assistant",
            "language": greeting_lang
        })
    except Exception as e:
        logger.error(f"Failed to generate greeting audio: {e}")
        await websocket.send_json({
            "event": "ai_speech",
            "text": greeting_text,
            "audio": None,
            "role": "assistant",
            "language": greeting_lang
        })

    # Step 2: Event loop for conversation
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "audio_input":
                audio_b64 = data.get("audio")
                if not audio_b64:
                    continue

                audio_bytes = base64.b64decode(audio_b64)
                await websocket.send_json({"event": "status", "message": "Listening & transcribing... (వింటున్నాను)"})

                # Transcribe user speech via Sarvam STT (auto-detects Telugu, Hindi, English)
                try:
                    user_text = await sarvam_client.speech_to_text(audio_bytes, language_code="unknown")
                except Exception as stt_err:
                    logger.error(f"STT error: {stt_err}")
                    user_text = ""

                # Ignore empty audio or ambient micro-clicks (<2 characters)
                if not user_text or len(user_text.strip()) < 2:
                    await websocket.send_json({
                        "event": "status",
                        "message": "🟢 వింటున్నాను... దయచేసి మాట్లాడండి (Listening... speak now)"
                    })
                    continue

                user_lang = detect_language(user_text)
                conversation_history.append({"role": "user", "content": user_text})
                await websocket.send_json({
                    "event": "user_speech",
                    "text": user_text,
                    "role": "user",
                    "language": user_lang
                })

                await websocket.send_json({"event": "status", "message": "🧠 సమాధానాన్ని అర్థం చేసుకుంటున్నాను... (Analyzing your response...)"})

                # Natural cognitive pause (500ms) - mimics human reflection and thought
                await asyncio.sleep(0.5)

                # Generate AI Sales Response matching customer's language
                ai_reply = await sales_agent.generate_response(conversation_history, lead_id=lead_id)
                conversation_history.append({"role": "assistant", "content": ai_reply})
                ai_lang = detect_language(ai_reply)

                # Synthesize Speech Audio in matched language
                await websocket.send_json({"event": "status", "message": "సమాధానం చెబుతున్నాను... (Speaking...)"})
                try:
                    speech_audio = await sarvam_client.text_to_speech(ai_reply, language_code=ai_lang)
                    speech_b64 = base64.b64encode(speech_audio).decode("utf-8")
                except Exception as tts_err:
                    logger.error(f"TTS error: {tts_err}")
                    speech_b64 = None

                await websocket.send_json({
                    "event": "ai_speech",
                    "text": ai_reply,
                    "audio": speech_b64,
                    "role": "assistant",
                    "language": ai_lang
                })

            elif event_type == "text_input":
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                user_lang = detect_language(user_text)
                conversation_history.append({"role": "user", "content": user_text})
                await websocket.send_json({
                    "event": "user_speech",
                    "text": user_text,
                    "role": "user",
                    "language": user_lang
                })

                await websocket.send_json({"event": "status", "message": "🧠 సమాధానాన్ని ఆలోచిస్తున్నాను... (Analyzing...)"})
                await asyncio.sleep(0.4)

                ai_reply = await sales_agent.generate_response(conversation_history, lead_id=lead_id)
                conversation_history.append({"role": "assistant", "content": ai_reply})
                ai_lang = detect_language(ai_reply)

                speech_b64 = None
                if data.get("generate_audio", True):
                    try:
                        speech_audio = await sarvam_client.text_to_speech(ai_reply, language_code=ai_lang)
                        speech_b64 = base64.b64encode(speech_audio).decode("utf-8")
                    except Exception as tts_err:
                        logger.error(f"TTS error: {tts_err}")

                await websocket.send_json({
                    "event": "ai_speech",
                    "text": ai_reply,
                    "audio": speech_b64,
                    "role": "assistant",
                    "language": ai_lang
                })

            elif event_type == "hangup":
                logger.info("Call hangup requested by client.")
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected from web call.")
    except Exception as e:
        logger.error(f"Web call exception: {e}")
    finally:
        # Step 3: Call Wrap-Up & Deal Intelligence Extraction
        duration = int(time.time() - start_time)
        logger.info(f"Call ended. Duration: {duration}s. Extracting sales intelligence...")

        try:
            intel = await sales_agent.extract_call_intelligence(conversation_history)
        except Exception as e:
            logger.error(f"Failed to extract intelligence: {e}")
            intel = {
                "summary": "Completed telephone conversation regarding software requirements.",
                "sentiment": "neutral",
                "deal_stage": "qualifying",
                "extracted_budget": "Not specified",
                "extracted_timeline": "Not specified",
                "extracted_requirements": "Software Services",
                "objections_raised": "None noted",
                "action_items": "Follow up with client."
            }

        call_record = {
            "lead_id": lead_id,
            "call_type": "web",
            "phone_number": call_lead.get("phone", "Web Browser") if call_lead else "Web Browser",
            "duration_seconds": duration,
            "status": "completed",
            "summary": intel.get("summary", ""),
            "sentiment": intel.get("sentiment", "neutral"),
            "deal_stage": intel.get("deal_stage", "qualifying"),
            "extracted_budget": intel.get("extracted_budget", ""),
            "extracted_timeline": intel.get("extracted_timeline", ""),
            "extracted_requirements": intel.get("extracted_requirements", ""),
            "objections_raised": intel.get("objections_raised", ""),
            "action_items": intel.get("action_items", ""),
            "transcript": json.dumps(conversation_history, ensure_ascii=False)
        }

        call_id = save_call_record(call_record)
        logger.info(f"Call recorded #{call_id}. Deal Stage: {intel.get('deal_stage')}")

        try:
            await websocket.send_json({
                "event": "call_summary",
                "call_id": call_id,
                "intelligence": intel,
                "duration": duration
            })
            await websocket.close()
        except Exception:
            pass


# =====================================================================
# TWILIO TELEPHONY WEBSOCKET (/ws/telephony)
# =====================================================================

@app.websocket("/ws/telephony")
async def websocket_telephony(websocket: WebSocket, lead_id: Optional[int] = Query(None)):
    """
    Twilio Media Streams WebSocket handler.
    Streams 8kHz mu-law audio bidirectionally for real phone calls.
    """
    await websocket.accept()
    logger.info(f"Twilio Telephony Media Stream connected. Lead: {lead_id}")

    stream_sid = None
    call_sid = None
    audio_buffer = bytearray()
    conversation_history: List[Dict[str, str]] = []
    start_time = time.time()
    call_lead = get_lead_by_id(lead_id) if lead_id else None

    # Helper to send mu-law audio chunk to Twilio
    async def send_audio_to_twilio(mulaw_chunk: bytes):
        payload = base64.b64encode(mulaw_chunk).decode("utf-8")
        media_message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload}
        }
        await websocket.send_text(json.dumps(media_message))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                call_sid = data["start"].get("callSid")
                logger.info(f"Twilio stream started: {stream_sid}, Call SID: {call_sid}")

                # Send initial greeting
                greeting = await sales_agent.get_initial_greeting(lead_id)
                conversation_history.append({"role": "assistant", "content": greeting})
                wav_audio = await sarvam_client.text_to_speech(greeting)
                mulaw_audio = wav_to_mulaw(wav_audio)
                await send_audio_to_twilio(mulaw_audio)

            elif event == "media":
                payload = data["media"]["payload"]
                raw_mulaw = base64.b64decode(payload)
                audio_buffer.extend(raw_mulaw)

                # Twilio sends 160 bytes every 20ms (8000 bytes/sec).
                # Buffer ~4.0 seconds (32,000 bytes) of conversational speech to prevent interrupting the caller
                if len(audio_buffer) >= 32000:
                    user_chunk = bytes(audio_buffer)
                    audio_buffer.clear()

                    wav_bytes = mulaw_to_wav(user_chunk)
                    try:
                        user_text = await sarvam_client.speech_to_text(wav_bytes, language_code="unknown")
                    except Exception as e:
                        logger.error(f"Telephony STT failed: {e}")
                        user_text = ""

                    if user_text and len(user_text.strip()) > 2:
                        conversation_history.append({"role": "user", "content": user_text})
                        # Thoughtful conversational pause
                        await asyncio.sleep(0.5)
                        ai_reply = await sales_agent.generate_response(conversation_history, lead_id=lead_id)
                        conversation_history.append({"role": "assistant", "content": ai_reply})

                        ai_lang = detect_language(ai_reply)
                        wav_reply = await sarvam_client.text_to_speech(ai_reply, language_code=ai_lang)
                        mulaw_reply = wav_to_mulaw(wav_reply)
                        await send_audio_to_twilio(mulaw_reply)

            elif event == "stop":
                logger.info("Twilio stream stopped.")
                break

    except WebSocketDisconnect:
        logger.info("Twilio stream disconnected.")
    except Exception as e:
        logger.error(f"Telephony error: {e}")
    finally:
        duration = int(time.time() - start_time)
        try:
            intel = await sales_agent.extract_call_intelligence(conversation_history)
        except Exception:
            intel = {
                "summary": "Completed telephone conversation with customer.",
                "deal_stage": "qualifying",
                "sentiment": "neutral",
                "extracted_requirements": "Software Services",
                "action_items": "Follow up with client."
            }

        save_call_record({
            "lead_id": lead_id,
            "call_type": "phone",
            "phone_number": call_lead.get("phone", "") if call_lead else "",
            "duration_seconds": duration,
            "status": "completed",
            "summary": intel.get("summary", ""),
            "sentiment": intel.get("sentiment", "neutral"),
            "deal_stage": intel.get("deal_stage", "qualifying"),
            "extracted_budget": intel.get("extracted_budget", ""),
            "extracted_timeline": intel.get("extracted_timeline", ""),
            "extracted_requirements": intel.get("extracted_requirements", ""),
            "objections_raised": intel.get("objections_raised", ""),
            "action_items": intel.get("action_items", ""),
            "transcript": json.dumps(conversation_history, ensure_ascii=False)
        })


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
