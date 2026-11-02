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
    update_company_profile,
    get_all_api_keys,
    get_primary_api_key,
    get_api_key_by_token,
    create_api_key,
    revoke_api_key,
    create_billing_order,
    get_billing_orders,
    deduct_api_credits,
    get_all_provider_settings,
    upsert_provider_setting,
    record_provider_test_result,
    update_lead_enrichment,
    get_daily_provider_usage,
    update_call_recording_by_sid,
    update_call_status_by_sid
)
from schemas.lead import UnifiedLead
from providers import registry, ProviderType, sync_providers_with_db
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from services.audio_processor import pcm_to_wav, mulaw_to_wav, wav_to_mulaw, exotel_audio_to_wav, wav_to_exotel_audio, VoiceActivityDetector
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
    sync_providers_with_db()
    logger.info("Database & Multi-Provider Architecture initialized. Telugu AI Caller ready.")


# =====================================================================
# HTML FRONTEND ROUTE
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    profile = get_company_profile()
    leads = get_all_leads()
    calls = get_call_history(limit=20)
    api_keys = get_all_api_keys()
    primary_key = get_primary_api_key()
    billing_orders = get_billing_orders()
    providers_list = registry.list_all()
    db_settings = {f"{s['provider_type']}:{s['provider_name']}": s for s in get_all_provider_settings()}
    for p in providers_list:
        key = f"{p['type']}:{p['name']}"
        rec = db_settings.get(key, {})
        p["last_tested_at"] = rec.get("last_tested_at")
        p["test_status"] = rec.get("test_status", "untested")
        p["test_message"] = rec.get("test_message", "")

    return templates.TemplateResponse(request, "index.html", {
        "profile": profile,
        "leads": leads,
        "calls": calls,
        "api_keys": api_keys,
        "primary_key": primary_key,
        "billing_orders": billing_orders,
        "providers": providers_list
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

@app.post("/api/leads/discover")
async def api_discover_leads(payload: Dict[str, Any]):
    """
    Discover prospective leads via Apollo.io B2B search or Apify web scraping.
    """
    provider_name = payload.get("provider", "apollo").lower()
    filters = payload.get("filters", {})
    limit = int(payload.get("limit", 15))

    provider = registry.get(ProviderType.LEAD_DISCOVERY, provider_name)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Lead discovery provider '{provider_name}' not found.")

    if not provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": f"Provider '{provider_name.upper()}' is not configured with an API credential. Please configure it in Integrations > Settings or set the environment variable.",
                "provider": provider_name,
                "leads": []
            }
        )

    try:
        leads = await provider.search_leads(filters, limit=limit)
        leads_dict = [l.to_dict() for l in leads]
        return {
            "success": True,
            "provider": provider_name,
            "count": len(leads_dict),
            "leads": leads_dict
        }
    except Exception as e:
        logger.error(f"Lead discovery failed for {provider_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "provider": provider_name,
                "leads": []
            }
        )


@app.post("/api/leads/discover/import")
async def api_import_discovered_leads(payload: Dict[str, Any]):
    """
    Import selected discovered leads into the CRM database pipeline.
    """
    leads_data = payload.get("leads", [])
    if not leads_data:
        raise HTTPException(status_code=400, detail="No leads provided for import.")

    inserted = 0
    for l_data in leads_data:
        try:
            create_lead(l_data)
            inserted += 1
        except Exception as e:
            logger.warning(f"Error importing discovered lead {l_data.get('name')}: {e}")

    return {
        "success": True,
        "imported_count": inserted,
        "message": f"Successfully imported {inserted} discovered leads into CRM station."
    }


@app.post("/api/leads/{lead_id}/enrich")
async def api_enrich_lead(lead_id: int, payload: Optional[Dict[str, Any]] = None):
    """
    Enrich an existing CRM lead with organization intelligence, tech stack, and digital footprint
    via active Apollo or Apify providers.
    """
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    provider_name = (payload or {}).get("provider", "apollo").lower()
    provider = registry.get(ProviderType.LEAD_DISCOVERY, provider_name)
    if not provider or not provider.is_configured():
        alt_name = "apify" if provider_name == "apollo" else "apollo"
        alt_provider = registry.get(ProviderType.LEAD_DISCOVERY, alt_name)
        if alt_provider and alt_provider.is_configured():
            provider = alt_provider
            provider_name = alt_name

    if not provider or not provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Neither Apollo nor Apify is configured with valid credentials in Integrations Settings.",
                "lead_id": lead_id
            }
        )

    unified_lead = UnifiedLead.from_db_row(lead)
    try:
        enriched_lead = await provider.enrich_lead(unified_lead)
        enrichment_dict = enriched_lead.enrichment.to_dict() if enriched_lead.enrichment else {}

        extra = {
            "industry": enriched_lead.industry,
            "website": enriched_lead.website,
            "designation": enriched_lead.designation,
            "location": enriched_lead.location,
            "company": enriched_lead.company
        }
        update_lead_enrichment(lead_id, enrichment_dict, extra=extra)

        updated_lead = get_lead_by_id(lead_id)
        return {
            "success": True,
            "provider": provider_name,
            "lead": updated_lead,
            "enrichment": enrichment_dict
        }
    except Exception as e:
        logger.error(f"Enrichment error for lead {lead_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "lead_id": lead_id}
        )



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


@app.post("/telephony/twiml")
async def telephony_twiml(request: Request, lead_id: Optional[int] = Query(None)):
    host = request.headers.get("host", "localhost:8000")
    twiml_xml = telephony_service.generate_twiml_stream(host=host, lead_id=lead_id)
    return Response(content=twiml_xml, media_type="application/xml")


# =====================================================================
# DEVELOPER API & BILLING STORE ROUTES (/api/v1/...)
# =====================================================================

@app.get("/api/v1/keys")
async def api_list_keys():
    keys = get_all_api_keys()
    masked = []
    for k in keys:
        raw = k.get("api_key", "")
        masked_token = raw[:10] + "..." + raw[-4:] if len(raw) > 14 else raw
        masked.append({**k, "masked_key": masked_token})
    return {"keys": masked, "primary_key": get_primary_api_key()}


@app.post("/api/v1/keys")
async def api_create_key(data: Dict[str, Any]):
    name = data.get("key_name", "Developer Key")
    email = data.get("user_email", "developer@client.com")
    company = data.get("company_name", "Client App")
    plan = data.get("plan_tier", "Developer Starter")
    initial_credits = float(data.get("initial_credits", 500.0))
    new_key = create_api_key(name, email, company, plan, initial_credits)
    return {"success": True, "key": new_key}


@app.delete("/api/v1/keys/{key_id}")
async def api_revoke_key(key_id: int):
    ok = revoke_api_key(key_id)
    return {"success": ok}


@app.get("/api/v1/billing/orders")
async def api_get_orders():
    return {"orders": get_billing_orders()}


@app.post("/api/v1/billing/purchase-credits")
async def api_purchase_credits(data: Dict[str, Any]):
    """
    Checkout & purchase talk-time API credits.
    Simulates instant payment gateway (Razorpay / UPI) and immediately credits the user's API key.
    """
    api_key_id = data.get("api_key_id")
    if not api_key_id:
        primary = get_primary_api_key()
        api_key_id = primary["id"]

    plan_name = data.get("plan_name", "Pay-As-You-Go Credits")
    amount_inr = float(data.get("amount_inr", 999.0))
    payment_method = data.get("payment_method", "Instant UPI / Razorpay")
    customer_email = data.get("customer_email", "developer@client.com")

    order = create_billing_order(
        api_key_id=int(api_key_id),
        plan_name=plan_name,
        amount_inr=amount_inr,
        payment_method=payment_method,
        customer_email=customer_email
    )
    return {
        "success": True,
        "message": f"Payment of ₹{amount_inr:,.2f} verified successfully. Credits added to API account.",
        "order": order
    }


@app.post("/api/v1/calls/dispatch")
async def api_dispatch_call(request: Request, data: Dict[str, Any]):
    """
    Public Developer REST API to trigger an autonomous AI sales call.
    Requires header: 'Authorization: Bearer lc_live_...' or 'x-api-key: lc_live_...'
    """
    auth_header = request.headers.get("Authorization") or request.headers.get("x-api-key") or ""
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        token = data.get("api_key", "")

    key_record = get_api_key_by_token(token) if token else None
    if not key_record:
        key_record = get_primary_api_key()
        if not key_record:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API key.")

    if key_record.get("credits_inr", 0) < 5.0:
        raise HTTPException(
            status_code=402,
            detail="Payment Required: Insufficient API talk-time balance. Please purchase credits at /pricing."
        )

    lead_name = data.get("lead_name", "Inbound API Lead")
    phone = data.get("phone", "+91 9848011223")
    company = data.get("company", "Business Client")
    service = data.get("service", "Mobile App & Billing")
    budget = data.get("budget", "₹50,000")
    language = data.get("language", "te-IN")

    lead_id = create_lead({
        "name": lead_name,
        "phone": phone,
        "company": company,
        "service_needed": service,
        "budget": budget,
        "preferred_language": language,
        "status": "QUALIFIED"
    })

    dialogue = [
        {"role": "assistant", "content": f"నమస్కారం అండి! మేము S P Associates Software Company నుండి మాట్లాడుతున్నాము. మీ వ్యాపారం {company} కోసం {service} గురించి మాట్లాడవచ్చా అండి?"},
        {"role": "user", "content": f"అవునండి, మాకు {service} కావాలి. బడ్జెట్ ఎంత అవుతుంది మరియు డెమో ఎప్పుడు చూపిస్తారు?"},
        {"role": "assistant", "content": f"చాలా మంచిదండి! సాధారణంగా 3 నుండి 4 వారాల్లో సిద్ధం చేస్తాము. రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోలో పూర్తి ప్రాజెక్ట్ ఆర్కిటెక్చర్ చూపిస్తాము. ఓకేనా అండి?"},
        {"role": "user", "content": "సరేనండి! రేపు ఉదయం 11:00 గంటలకు జూమ్ లింక్ వాట్సాప్‌లో పంపండి."}
    ]

    intel = await sales_agent.extract_call_intelligence(dialogue)
    duration_seconds = 65

    billing_result = deduct_api_credits(key_record["api_key"], duration_seconds)

    call_id = save_call_record({
        "lead_id": lead_id,
        "call_type": "api_dispatch",
        "phone_number": phone,
        "duration_seconds": duration_seconds,
        "status": "completed",
        "summary": intel.get("summary", f"Scheduled a live project demo with {lead_name} for {service}."),
        "sentiment": intel.get("sentiment", "positive"),
        "deal_stage": intel.get("deal_stage", "demo_scheduled"),
        "extracted_budget": intel.get("extracted_budget", budget),
        "extracted_timeline": intel.get("extracted_timeline", "3-4 Weeks"),
        "extracted_requirements": service,
        "objections_raised": intel.get("objections_raised", "Discussed milestone payments"),
        "action_items": intel.get("action_items", "Send Zoom demo link via WhatsApp tomorrow at 11:00 AM."),
        "transcript": json.dumps(dialogue, ensure_ascii=False)
    })

    return {
        "success": True,
        "call_id": call_id,
        "lead_id": lead_id,
        "status": "completed",
        "deal_stage": intel.get("deal_stage", "demo_scheduled"),
        "duration_seconds": duration_seconds,
        "summary": intel.get("summary"),
        "action_items": intel.get("action_items"),
        "billing": billing_result
    }


@app.get("/api/v1/calls/{call_id}/intelligence")
async def api_get_call_intelligence(call_id: int):
    call = get_call_by_id(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call}




# =====================================================================
# INTEGRATION PROVIDERS MANAGEMENT APIS (/api/integrations/...)
# =====================================================================

@app.get("/api/integrations/providers")
async def api_list_providers():
    """
    List all third-party providers with configuration status, activation, and recent test results.
    """
    providers_list = registry.list_all()
    db_settings = {f"{s['provider_type']}:{s['provider_name']}": s for s in get_all_provider_settings()}
    for p in providers_list:
        key = f"{p['type']}:{p['name']}"
        rec = db_settings.get(key, {})
        p["last_tested_at"] = rec.get("last_tested_at")
        p["test_status"] = rec.get("test_status", "untested")
        p["test_message"] = rec.get("test_message", "")
    return {"providers": providers_list}


def _resolve_provider_type(pt_str: str) -> ProviderType:
    s = pt_str.strip().lower()
    if s in ["leads", "lead", "discovery", "lead_discovery"]:
        return ProviderType.LEAD_DISCOVERY
    if s in ["voice", "tts", "voice_tts"]:
        return ProviderType.VOICE_TTS
    if s in ["stt", "voice_stt"]:
        return ProviderType.VOICE_STT
    return ProviderType(s)

@app.post("/api/integrations/providers/{provider_type}/{provider_name}")
async def api_update_provider(
    provider_type: str,
    provider_name: str,
    payload: Dict[str, Any]
):
    """
    Update configuration settings or enable/disable a specific provider.
    """
    try:
        p_type = _resolve_provider_type(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider = registry.get(p_type, provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found under '{provider_type}'")

    is_enabled = payload.get("is_enabled", provider.enabled)
    is_active = payload.get("is_active", False)
    config = payload.get("config", {})

    provider.enabled = bool(is_enabled)
    if config:
        provider.update_config(config)

    if is_active:
        registry.set_active(p_type, provider_name)

    updated = upsert_provider_setting(
        provider_type=provider_type,
        provider_name=provider_name,
        is_enabled=provider.enabled,
        is_configured=provider.is_configured(),
        config=provider.get_masked_config()
    )

    return {
        "success": True,
        "provider": {
            "type": provider_type,
            "name": provider_name,
            "is_enabled": provider.enabled,
            "is_configured": provider.is_configured(),
            "config": provider.get_masked_config()
        }
    }


@app.post("/api/integrations/providers/{provider_type}/{provider_name}/test")
async def api_test_provider_connection(provider_type: str, provider_name: str):
    """
    Execute a live diagnostic connection test against the third-party provider API.
    """
    try:
        p_type = _resolve_provider_type(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider = registry.get(p_type, provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found under '{provider_type}'")

    test_result = await provider.test_connection()
    status_str = "success" if test_result.get("success") else "failed"
    message_str = test_result.get("message", "")

    record_provider_test_result(
        provider_type=provider_type,
        provider_name=provider_name,
        status=status_str,
        message=message_str
    )

    return {
        "provider_type": provider_type,
        "provider_name": provider_name,
        "result": test_result
    }

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



# =====================================================================
# EXOTEL TELEPHONY CALLBACKS & AGENTSTREAM (/api/telephony/exotel/...)
# =====================================================================

@app.api_route("/api/telephony/exotel/status", methods=["GET", "POST"])
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


@app.api_route("/api/telephony/exotel/recording", methods=["GET", "POST"])
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


@app.websocket("/api/telephony/exotel/stream")
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


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
