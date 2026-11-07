"""
Quotations, Price Book & WhatsApp Compliance Router (Plan v2 §5 & §6).
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Body, HTTPException, Request, Response

from core.auth import get_request_account_id, get_optional_user
from database import get_lead_by_id, update_lead, add_opt_out, get_all_leads
from services.quotation_service import (
    get_price_book,
    upsert_price_book_item,
    create_quotation,
    list_quotations,
    get_quotation,
    approve_quotation,
    update_quotation_status,
    evaluate_quote_followup_needed,
    generate_quotation_pdf_bytes,
    is_whatsapp_stop_message,
)

router = APIRouter()


@router.get("/api/price-book")
async def api_get_price_book(request: Request):
    """Returns the standard price book for the account (§5)."""
    acc_id = get_request_account_id(request) or 1
    items = get_price_book(account_id=acc_id)
    return {"status": "success", "items": items, "count": len(items)}


@router.post("/api/price-book")
async def api_upsert_price_book(request: Request, payload: Dict[str, Any] = Body(...)):
    """Adds or updates a package in the account's price book (§5)."""
    user = get_optional_user(request)
    if user and user.get("role") not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner or admin can edit the price book")
    acc_id = (user["account_id"] if user else None) or get_request_account_id(request) or 1
    item = upsert_price_book_item(payload, account_id=acc_id)
    return {"status": "success", "item": item}


@router.get("/api/quotations")
async def api_list_quotations(
    request: Request,
    lead_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """Lists quotations for the account with optional lead_id or status filter."""
    acc_id = get_request_account_id(request) or 1
    quotes = list_quotations(account_id=acc_id, lead_id=lead_id, status=status)
    return {"status": "success", "quotations": quotes, "count": len(quotes)}


@router.post("/api/quotations")
async def api_create_quotation(request: Request, payload: Dict[str, Any] = Body(...)):
    """
    Creates a quotation from the price book with Plan v2 §5 guardrails:
    - Standard package within discount limit -> auto-approved (`sent` or `approved_ready`)
    - Custom scope or discount > max_discount_pct -> `pending_approval` (manager approval required)
    """
    acc_id = get_request_account_id(request) or 1
    user = get_optional_user(request)
    lead_id = int(payload.get("lead_id") or 0)
    lead = get_lead_by_id(lead_id, account_id=acc_id) if lead_id else None

    lead_name = str(payload.get("lead_name") or (lead.get("name") if lead else None) or "Valued Client")
    lead_phone = str(payload.get("lead_phone") or (lead.get("phone") if lead else None) or "+910000000000")
    whatsapp_opt_in = bool(
        payload.get("whatsapp_opt_in")
        if "whatsapp_opt_in" in payload
        else (lead.get("whatsapp_opt_in", False) if lead else False)
    )

    quote = create_quotation(
        lead_id=lead_id,
        lead_name=lead_name,
        lead_phone=lead_phone,
        package_code=str(payload.get("package_code") or "pkg_starter"),
        discount_pct=float(payload.get("discount_pct", 0.0) or 0.0),
        is_custom_scope=bool(payload.get("is_custom_scope", False)),
        custom_scope_notes=str(payload.get("custom_scope_notes") or ""),
        custom_price_inr=payload.get("custom_price_inr"),
        validity_days=int(payload.get("validity_days", 7) or 7),
        whatsapp_opt_in=whatsapp_opt_in,
        account_id=acc_id,
        created_by=str((user.get("email") if user else None) or payload.get("created_by") or "ai_agent"),
    )

    if lead_id and lead:
        update_lead(
            lead_id,
            {"status": "QUOTE_SENT" if quote["status"] == "sent" else lead.get("status", "QUALIFIED")},
            account_id=acc_id,
        )

    return {"status": "success", "quotation": quote}


@router.post("/api/quotations/{quote_id}/approve")
async def api_approve_quotation(quote_id: int, request: Request):
    """Manager one-tap approval for custom scope or high-discount quotations (§5)."""
    user = get_optional_user(request)
    if user and user.get("role") not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only manager (owner/admin) can approve quotations")
    acc_id = (user["account_id"] if user else None) or get_request_account_id(request) or 1
    manager_email = (user.get("email") if user else None) or "owner@spassociates.com"

    quote = approve_quotation(quote_id, manager_email=manager_email, account_id=acc_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return {"status": "success", "quotation": quote}


@router.post("/api/quotations/{quote_id}/status")
async def api_update_quotation_status(
    quote_id: int,
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    """Updates quotation lifecycle (`opened`, `won`, `lost`, `rejected`) and syncs lead stage."""
    acc_id = get_request_account_id(request) or 1
    new_status = (payload.get("status") or "").strip().lower()
    if new_status not in {"sent", "opened", "won", "lost", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid quotation status")

    quote = update_quotation_status(
        quote_id=quote_id,
        new_status=new_status,
        lost_reason=payload.get("lost_reason"),
        won_amount_inr=payload.get("won_amount_inr"),
        account_id=acc_id,
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    lead_id = quote.get("lead_id")
    if lead_id:
        if new_status == "won":
            update_lead(lead_id, {"status": "CLOSED_WON"}, account_id=acc_id)
        elif new_status == "lost":
            update_lead(lead_id, {"status": "LOST", "notes": payload.get("lost_reason", "")}, account_id=acc_id)

    followup_eval = evaluate_quote_followup_needed(quote)
    return {"status": "success", "quotation": quote, "followup_evaluation": followup_eval}


@router.get("/api/quotations/{quote_id}/pdf")
async def api_download_quotation_pdf(quote_id: int, request: Request):
    """Generates and returns the branded PDF for a quotation (§5)."""
    acc_id = get_request_account_id(request) or 1
    quote = get_quotation(quote_id, account_id=acc_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    pdf_bytes = generate_quotation_pdf_bytes(quote)
    filename = f"{quote['quote_number']}_v{quote['version']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/quotations/whatsapp/incoming")
async def api_whatsapp_incoming_webhook(request: Request, payload: Dict[str, Any] = Body(...)):
    """
    Handles incoming WhatsApp replies (§6):
    - If message is 'STOP' / 'UNSUBSCRIBE' / 'DND', immediately adds phone to opt_outs
      and halts all future calls & WhatsApp messages.
    """
    acc_id = get_request_account_id(request) or 1
    phone = (payload.get("phone") or payload.get("from") or "").strip()
    message_text = (payload.get("message") or payload.get("text") or "").strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    if is_whatsapp_stop_message(message_text):
        opt = add_opt_out(phone=phone, reason="whatsapp_stop", account_id=acc_id)
        return {
            "status": "success",
            "action": "opted_out",
            "phone_e164": opt["phone_e164"],
            "message": "STOP honoured: lead added to Do-Not-Call & WhatsApp opt-out list forever.",
        }

    # Check if this phone belongs to an active lead and mark quote replied
    all_leads = get_all_leads(account_id=acc_id)
    leads = [l for l in all_leads if phone[-10:] in str(l.get("phone") or "")]
    lead_id = leads[0]["id"] if leads else None
    if lead_id:
        for q in list_quotations(account_id=acc_id, lead_id=lead_id):
            q["replied_at"] = q.get("updated_at")

    return {
        "status": "success",
        "action": "message_logged",
        "lead_id": lead_id,
    }
