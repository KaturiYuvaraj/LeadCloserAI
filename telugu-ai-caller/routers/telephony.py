import json
import base64
import time
import asyncio
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Query, HTTPException
from fastapi.responses import JSONResponse, Response
from loguru import logger

from database import (
    get_lead_by_id,
    update_lead,
    save_call_record,
    update_call_recording_by_sid,
    update_call_status_by_sid
)
from providers import registry, ProviderType
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from services.audio_processor import (
    pcm_to_wav,
    mulaw_to_wav,
    wav_to_mulaw,
    exotel_audio_to_wav,
    wav_to_exotel_audio,
    VoiceActivityDetector
)
from services.telephony_service import telephony_service
from services.language_utils import detect_language

router = APIRouter()


@router.post("/api/call/outbound")
async def api_outbound_call(payload: Dict[str, Any], request: Request):
    to_phone = payload.get("phone")
    lead_id = payload.get("lead_id")
    provider_override = payload.get("provider")
    if not to_phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    host = request.headers.get("host")

    # Check requested or active telephony provider
    telephony_provider = None
    if provider_override:
        telephony_provider = registry.get(ProviderType.TELEPHONY, provider_override.lower())
    if not telephony_provider:
        telephony_provider = registry.get_active(ProviderType.TELEPHONY)

    if telephony_provider and telephony_provider.is_configured():
        logger.info(f"Initiating outbound call via active provider '{telephony_provider.name}'")
        result = await telephony_provider.initiate_outbound_call(
            to_phone=to_phone,
            lead_id=lead_id,
            callback_host=host
        )
        return result

    result = await telephony_service.initiate_outbound_call(
        to_phone=to_phone,
        lead_id=lead_id,
        webhook_host=host
    )
    return result


@router.post("/telephony/twiml")
async def telephony_twiml(request: Request, lead_id: Optional[int] = Query(None)):
    host = request.headers.get("host", "localhost:8000")
    twiml_xml = telephony_service.generate_twiml_stream(host=host, lead_id=lead_id)
    return Response(content=twiml_xml, media_type="application/xml")


# =====================================================================
# INTERACTIVE BROWSER CALL WEBSOCKET (/ws/web-call)
# =====================================================================

@router.websocket("/ws/web-call")
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

@router.websocket("/ws/telephony")
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


# =====================================================================
# EXOTEL TELEPHONY CALLBACKS & AGENTSTREAM (/api/telephony/exotel/...)
# =====================================================================

@router.api_route("/api/telephony/exotel/status", methods=["GET", "POST"])
async def exotel_call_status(request: Request):
    """
    Exotel status callback webhook: receives terminal call dispositions
    (completed, busy, no-answer, failed, canceled).
    """
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            form = await request.form()
            params.update(dict(form))
        except Exception:
            pass

    call_sid = params.get("CallSid") or params.get("CallId") or params.get("Sid")
    status = params.get("Status") or params.get("CallStatus") or "completed"
    duration = int(params.get("Duration") or params.get("CallDuration") or 0)
    recording_url = params.get("RecordingUrl") or params.get("RecordingUrlHttps")

    logger.info(f"Exotel call callback: SID={call_sid}, status={status}, duration={duration}s")

    if call_sid:
        update_call_status_by_sid(call_sid=call_sid, status=status, duration=duration)
        if recording_url:
            update_call_recording_by_sid(call_sid=call_sid, recording_url=recording_url)

    lead_id = params.get("lead_id") or params.get("CustomField")
    if lead_id and status in ["busy", "no-answer", "failed"]:
        try:
            lead = get_lead_by_id(int(lead_id))
            if lead:
                existing_notes = lead.get("notes") or ""
                update_lead(int(lead_id), {
                    "notes": f"{existing_notes} [PSTN Call attempt: {status.upper()}]".strip()
                })
        except Exception as e:
            logger.warning(f"Could not update lead {lead_id} from Exotel callback: {e}")

    return JSONResponse(content={"status": "received", "call_sid": call_sid, "disposition": status})


@router.api_route("/api/telephony/exotel/recording", methods=["GET", "POST"])
async def exotel_recording_callback(request: Request):
    """
    Exotel recording callback webhook: captures authenticated recording URL.
    """
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            form = await request.form()
            params.update(dict(form))
        except Exception:
            pass

    call_sid = params.get("CallSid") or params.get("CallId") or params.get("Sid")
    recording_url = params.get("RecordingUrl") or params.get("RecordingUrlHttps")

    if call_sid and recording_url:
        update_call_recording_by_sid(call_sid=call_sid, recording_url=recording_url)
        logger.info(f"Saved recording URL for Exotel call {call_sid}: {recording_url}")

    return JSONResponse(content={"status": "saved", "call_sid": call_sid})


@router.websocket("/api/telephony/exotel/stream")
async def websocket_exotel_agentstream(websocket: WebSocket, lead_id: Optional[int] = Query(None)):
    """
    Exotel AgentStream bidirectional WebSocket endpoint.
    Handles real-time audio streaming (G.711 mu-law or 16-bit PCM),
    interruptions, and conversational audio turn-taking with VAD.
    """
    await websocket.accept()
    logger.info(f"Exotel AgentStream WebSocket connected. Lead ID: {lead_id}")

    stream_id = None
    call_id = None
    encoding = "audio/x-mulaw"
    sample_rate = 8000
    vad = None
    ai_is_speaking = False
    conversation_history: List[Dict[str, str]] = []
    start_time = time.time()
    call_lead = get_lead_by_id(lead_id) if lead_id else None

    async def send_audio_chunk_to_exotel(audio_bytes: bytes):
        payload = base64.b64encode(audio_bytes).decode("utf-8")
        msg = {
            "event": "media",
            "stream_id": stream_id,
            "media": {
                "payload": payload
            }
        }
        await websocket.send_text(json.dumps(msg))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event in ["connected", "start"]:
                stream_id = data.get("stream_id") or data.get("streamSid") or (data.get("start", {}).get("streamSid"))
                call_id = data.get("call_id") or data.get("callSid") or (data.get("start", {}).get("callSid"))
                media_format = data.get("media_format") or (data.get("start", {}).get("mediaFormat")) or {}
                encoding = media_format.get("encoding", "audio/x-mulaw")
                sample_rate = int(media_format.get("sample_rate", 8000))

                vad = VoiceActivityDetector(energy_threshold=450, silence_duration_ms=750, sample_rate=sample_rate)
                logger.info(f"Exotel AgentStream started: stream_id={stream_id}, call_id={call_id}, format={encoding}@{sample_rate}Hz")

                greeting = await sales_agent.get_initial_greeting(lead_id)
                conversation_history.append({"role": "assistant", "content": greeting})
                wav_audio = await sarvam_client.text_to_speech(greeting)
                exotel_audio = wav_to_exotel_audio(wav_audio, encoding=encoding, target_rate=sample_rate)
                ai_is_speaking = True
                await send_audio_chunk_to_exotel(exotel_audio)

            elif event == "media":
                media_obj = data.get("media", {})
                payload = media_obj.get("payload", "")
                raw_audio = base64.b64decode(payload)

                import audioop
                if "mulaw" in encoding.lower() or "ulaw" in encoding.lower():
                    pcm_frame = audioop.ulaw2lin(raw_audio, 2)
                else:
                    pcm_frame = raw_audio

                vad_state = vad.process_frame(pcm_frame) if vad else {"is_speech": False, "end_of_turn": False, "barge_in": False}

                # Interruption / Barge-in detection
                if vad_state["barge_in"] and ai_is_speaking:
                    logger.info(f"Barge-in detected: interrupting AI speech on stream {stream_id}")
                    ai_is_speaking = False
                    await websocket.send_text(json.dumps({"event": "clear", "stream_id": stream_id}))

                # End of turn detection (VAD silence threshold or buffer limit)
                if vad_state["end_of_turn"] or (vad and len(vad.speech_buffer) >= (sample_rate * 2 * 4)):
                    speech_pcm = vad.get_speech_bytes() if vad else b""
                    if len(speech_pcm) >= 1600:
                        wav_bytes = pcm_to_wav(speech_pcm, sample_rate=sample_rate)
                        t_start = time.time()
                        try:
                            user_text = await sarvam_client.speech_to_text(wav_bytes, language_code="unknown")
                        except Exception as e:
                            logger.error(f"Exotel STT error: {e}")
                            user_text = ""
                        stt_ms = round((time.time() - t_start) * 1000, 1)

                        if user_text and len(user_text.strip()) > 2:
                            conversation_history.append({"role": "user", "content": user_text})
                            await asyncio.sleep(0.3)

                            t_llm = time.time()
                            ai_reply = await sales_agent.generate_response(conversation_history, lead_id=lead_id)
                            conversation_history.append({"role": "assistant", "content": ai_reply})
                            llm_ms = round((time.time() - t_llm) * 1000, 1)

                            t_tts = time.time()
                            ai_lang = detect_language(ai_reply)
                            wav_reply = await sarvam_client.text_to_speech(ai_reply, language_code=ai_lang)
                            exotel_reply = wav_to_exotel_audio(wav_reply, encoding=encoding, target_rate=sample_rate)
                            tts_ms = round((time.time() - t_tts) * 1000, 1)

                            total_ms = round((time.time() - t_start) * 1000, 1)
                            logger.info(f"[EXOTEL LATENCY] Turnaround: {total_ms}ms (STT: {stt_ms}ms, LLM: {llm_ms}ms, TTS: {tts_ms}ms)")

                            ai_is_speaking = True
                            await send_audio_chunk_to_exotel(exotel_reply)

            elif event in ["clear", "interruption"]:
                logger.info(f"Exotel stream interruption received for stream {stream_id}")
                if vad:
                    vad.reset()
                ai_is_speaking = False

            elif event == "stop":
                logger.info(f"Exotel AgentStream stopped for stream {stream_id}")
                break

    except WebSocketDisconnect:
        logger.info("Exotel AgentStream client disconnected.")
    except Exception as e:
        logger.error(f"Exotel AgentStream error: {e}")
    finally:
        duration = int(time.time() - start_time)
        try:
            intel = await sales_agent.extract_call_intelligence(conversation_history)
        except Exception:
            intel = {
                "summary": "Completed telephone conversation via Exotel carrier.",
                "deal_stage": "qualifying",
                "sentiment": "neutral",
                "extracted_requirements": "Software Services",
                "action_items": "Follow up with customer."
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
            "transcript": json.dumps(conversation_history, ensure_ascii=False),
            "call_sid": call_id or ""
        })

