"""
Developer Router - API keys, billing history and the call intelligence API.

28 Nov 2026 (GeniusBot as a platform for many companies): every route works only on the signed-in company's
own records. Removed:
  - "purchase-credits", which added credits without taking any payment (payments go through Razorpay)
  - the free Rs 2,500 / Rs 500 on every new API key
  - "/api/v1/calls/dispatch", which never placed a call: it invented a conversation, saved it as a real call
    and charged credits. It answers 501 until real calls are wired for customer accounts.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import get_current_user, get_optional_user
from database import (
    create_api_key,
    get_all_api_keys,
    get_api_key_by_token,
    get_billing_orders,
    get_call_by_id,
    get_primary_api_key,
    revoke_api_key,
)

router = APIRouter(tags=["developer"])


def _mask(raw: str) -> str:
    return raw[:10] + "..." + raw[-4:] if raw and len(raw) > 14 else "••••"


def _masked(key: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in key.items() if k != "api_key"}
    out["masked_key"] = _mask(key.get("api_key", ""))
    return out


@router.get("/api/v1/keys")
async def api_list_keys(user: Dict[str, Any] = Depends(get_current_user)):
    acc_id = int(user["account_id"])
    keys = [_masked(k) for k in get_all_api_keys(account_id=acc_id)]
    primary = get_primary_api_key(account_id=acc_id)
    return {"keys": keys, "primary_key": _masked(primary) if primary else None}


@router.post("/api/v1/keys")
async def api_create_key(data: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    key = create_api_key({
        "key_name": str(data.get("key_name") or "Developer Key")[:120],
        "user_email": user.get("email") or "",
        "company_name": str(data.get("company_name") or "")[:200],
    }, account_id=int(user["account_id"]))
    return {"success": True, "key": key, "note": "Copy this key now: it is shown only once."}


@router.delete("/api/v1/keys/{key_id}")
async def api_revoke_key(key_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    if not revoke_api_key(key_id=key_id, account_id=int(user["account_id"])):
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"success": True}


@router.get("/api/v1/billing/orders")
async def api_get_orders(user: Dict[str, Any] = Depends(get_current_user)):
    return {"orders": get_billing_orders(account_id=int(user["account_id"]))}


@router.post("/api/v1/billing/purchase-credits")
async def api_purchase_credits(user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=410, detail="Top-ups are made through the secure Razorpay checkout.")


@router.post("/api/v1/calls/dispatch")
async def api_dispatch_call():
    raise HTTPException(status_code=501, detail="Placing calls through the API is not available yet.")


@router.get("/api/v1/calls/{call_id}/intelligence")
async def api_get_call_intelligence(call_id: int, request: Request):
    """A call of the signed-in company, or of the company that owns the API key."""
    auth_header = request.headers.get("Authorization") or request.headers.get("x-api-key") or ""
    token = auth_header.replace("Bearer ", "").strip()
    account_id = None
    if token.startswith("lc_"):
        key = get_api_key_by_token(token)
        if key and key.get("status") == "active":
            account_id = key.get("account_id")
    if account_id is None:
        try:
            user = get_optional_user(request)
        except HTTPException:
            user = None
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized: sign in or send a valid API key.")
        account_id = user["account_id"]
    call = get_call_by_id(call_id, account_id=int(account_id))
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"call": call}
