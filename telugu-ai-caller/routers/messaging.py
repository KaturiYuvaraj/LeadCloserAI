"""
Messaging & Calendar Router - Meta WhatsApp Cloud API & Google Calendar Scheduling
"""
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from database import get_all_leads, get_lead_by_id, update_lead
from providers import registry, ProviderType

router = APIRouter(tags=["messaging"])


@router.get("/api/webhooks/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """Meta webhook verification endpoint."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "sp_associates_leadcloser_webhook")
    if mode == "subscribe" and token == verify_token:
        logger.info("WhatsApp webhook verified successfully.")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/api/webhooks/whatsapp")
async def handle_whatsapp_webhook(request: Request):
    """Inbound WhatsApp message and status callback processor."""
    try:
        data = await request.json()
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0].get("value", {})
        messages = changes.get("messages", [])
        if messages:
            msg = messages[0]
            from_phone = msg.get("from")
            text = msg.get("text", {}).get("body", "")
            logger.info(f"Inbound WhatsApp message from {from_phone}: {text}")
            all_leads = get_all_leads()
            for l in all_leads:
                if l.get("phone") and l["phone"].replace("+", "").replace(" ", "").endswith(from_phone[-10:]):
                    cur_notes = l.get("notes") or ""
                    update_lead(l["id"], {"notes": f"{cur_notes} [WhatsApp reply: {text}]".strip()})
                    break
        return {"status": "processed"}
    except Exception as e:
        logger.warning(f"Error processing WhatsApp webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/messaging/whatsapp/send")
async def api_send_whatsapp_message(payload: Dict[str, Any]):
    """Send WhatsApp message or template to a lead."""
    lead_id = payload.get("lead_id")
    to_phone = payload.get("phone")
    message = payload.get("message", "")

    if lead_id and not to_phone:
        lead = get_lead_by_id(lead_id)
        if lead:
            to_phone = lead.get("phone")

    if not to_phone:
        raise HTTPException(status_code=400, detail="Recipient phone number is required.")

    whatsapp_provider = registry.get(ProviderType.MESSAGING, "meta_whatsapp")
    if not whatsapp_provider:
        raise HTTPException(status_code=400, detail="Meta WhatsApp provider not found.")

    if not whatsapp_provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "WhatsApp credentials (WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN) are not configured. Please configure in Integrations > Settings."
            }
        )

    res = await whatsapp_provider.send_text_message(to_phone=to_phone, message=message)
    if res.get("success") and lead_id:
        lead = get_lead_by_id(lead_id)
        if lead:
            cur_notes = lead.get("notes") or ""
            update_lead(lead_id, {"notes": f"{cur_notes} [Sent WhatsApp: {message[:60]}...]".strip()})

    return res


@router.post("/api/calendar/book")
async def api_book_calendar_meeting(payload: Dict[str, Any]):
    """Book a Google Calendar demo meeting with Google Meet link."""
    lead_id = payload.get("lead_id")
    title = payload.get("title", "S P Associates — Software Scoping & Demo Call")
    start_time = payload.get("start_time")
    duration = int(payload.get("duration_minutes", 15))
    customer_email = payload.get("email")
    customer_name = payload.get("name")

    if lead_id:
        lead = get_lead_by_id(lead_id)
        if lead:
            if not customer_email:
                customer_email = lead.get("email")
            if not customer_name:
                customer_name = lead.get("name")

    calendar_provider = registry.get(ProviderType.CALENDAR, "google_calendar")
    if not calendar_provider:
        raise HTTPException(status_code=400, detail="Google Calendar provider not found.")

    if not calendar_provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Google Calendar OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN) are not configured. Please configure in Integrations > Settings."
            }
        )

    res = await calendar_provider.book_meeting(
        title=title,
        start_time=start_time,
        duration_minutes=duration,
        customer_email=customer_email,
        customer_name=customer_name
    )

    if res.get("success") and lead_id:
        meet_link = res.get("meet_link", "")
        update_lead(lead_id, {
            "status": "DEMO_BOOKED",
            "action_items": f"Live Demo Scheduled: {start_time} (Meet: {meet_link})".strip()
        })

    return res


@router.get("/api/calendar/availability")
async def api_check_calendar_availability(start_time: str, end_time: str):
    """Check busy time slots on Google Calendar."""
    calendar_provider = registry.get(ProviderType.CALENDAR, "google_calendar")
    if not calendar_provider or not calendar_provider.is_configured():
        return {"busy_slots": []}

    slots = await calendar_provider.check_availability(start_time=start_time, end_time=end_time)
    return {"busy_slots": slots}

