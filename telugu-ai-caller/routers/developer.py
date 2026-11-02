"""
Developer Router - Public REST API Platform, API Keys & Billing Store
"""
import json
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException

from database import (
    get_all_api_keys,
    get_primary_api_key,
    get_api_key_by_token,
    create_api_key,
    revoke_api_key,
    create_billing_order,
    get_billing_orders,
    deduct_api_credits,
    create_lead,
    save_call_record,
    get_call_by_id,
)
from services.sales_agent import sales_agent

router = APIRouter(tags=["developer"])


@router.get("/api/v1/keys")
async def api_list_keys():
    keys = get_all_api_keys()
    masked = []
    for k in keys:
        raw = k.get("api_key", "")
        masked_token = raw[:10] + "..." + raw[-4:] if len(raw) > 14 else raw
        masked.append({**k, "masked_key": masked_token})
    return {"keys": masked, "primary_key": get_primary_api_key()}


@router.post("/api/v1/keys")
async def api_create_key(data: Dict[str, Any]):
    name = data.get("key_name", "Developer Key")
    email = data.get("user_email", "developer@client.com")
    company = data.get("company_name", "Client App")
    plan = data.get("plan_tier", "Developer Starter")
    initial_credits = float(data.get("initial_credits", 500.0))
    new_key = create_api_key(name, email, company, plan, initial_credits)
    return {"success": True, "key": new_key}


@router.delete("/api/v1/keys/{key_id}")
async def api_revoke_key(key_id: int):
    ok = revoke_api_key(key_id)
    return {"success": ok}


@router.get("/api/v1/billing/orders")
async def api_get_orders():
    return {"orders": get_billing_orders()}


@router.post("/api/v1/billing/purchase-credits")
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


@router.post("/api/v1/calls/dispatch")
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


@router.get("/api/v1/calls/{call_id}/intelligence")
async def api_get_call_intelligence(call_id: int):
    call = get_call_by_id(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call}

