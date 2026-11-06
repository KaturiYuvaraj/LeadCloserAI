"""
Pages Router - Separate Landing Page (Homepage) and Dedicated CRM Dashboard
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from core.auth import get_optional_user, get_request_account_id
from core.web import templates
from database import (
    get_company_profile,
    get_all_leads,
    get_call_history,
    get_all_api_keys,
    get_primary_api_key,
    get_billing_orders,
    get_all_ai_employees,
    get_active_ai_employee,
    get_outcome_bucket_summary,
)

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def serve_landing(request: Request):
    """
    Public SaaS Marketing Homepage (Outpero luxury architectural design).
    Features AI voice synthesizer demo, 5 AI personas, feature highlights & pricing.
    """
    profile = get_company_profile()
    api_keys = get_all_api_keys()
    primary_key = get_primary_api_key()
    employees = get_all_ai_employees()
    active_emp = get_active_ai_employee()
    return templates.TemplateResponse(request, "index.html", {
        "profile": profile,
        "api_keys": api_keys,
        "primary_key": primary_key,
        "employees": employees,
        "active_employee": active_emp
    })


@router.get("/crm", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/calling", response_class=HTMLResponse)
@router.get("/leads", response_class=HTMLResponse)
@router.get("/campaigns", response_class=HTMLResponse)
@router.get("/automations", response_class=HTMLResponse)
@router.get("/analytics", response_class=HTMLResponse)
async def serve_crm(request: Request):
    """
    Dedicated CRM Application Shell.
    Redirects unauthenticated users to /login immediately.
    """
    current_user = get_optional_user(request)
    if not current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login?next=" + request.url.path, status_code=302)
    account_id = get_request_account_id(request)
    profile = get_company_profile()
    leads = get_all_leads(account_id=account_id)
    calls = get_call_history(limit=20, account_id=account_id)
    outcome_summary = get_outcome_bucket_summary(account_id=account_id)
    api_keys = get_all_api_keys()
    primary_key = get_primary_api_key()
    billing_orders = get_billing_orders()
    employees = get_all_ai_employees()
    active_emp = get_active_ai_employee()

    import os
    from config import VOBIZ_CALLER_ID, SARVAM_API_KEY, DIALER_PROVIDER, VOBIZ_AUTH_ID
    vobiz_caller_id = os.getenv("VOBIZ_CALLER_ID", VOBIZ_CALLER_ID)
    sarvam_key = os.getenv("SARVAM_API_KEY", SARVAM_API_KEY)
    sarvam_key_masked = sarvam_key[:6] + "****" + sarvam_key[-4:] if len(sarvam_key) > 10 else "Active"
    vobiz_auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
    vobiz_auth_id_masked = vobiz_auth_id[:4] + "****" + vobiz_auth_id[-4:] if len(vobiz_auth_id) > 8 else "Active"
    dialer_provider = os.getenv("DIALER_PROVIDER", DIALER_PROVIDER)

    return templates.TemplateResponse(request, "crm.html", {
        "profile": profile,
        "leads": leads,
        "calls": calls,
        "outcome_summary": outcome_summary,
        "current_user": current_user,
        "api_keys": api_keys,
        "primary_key": primary_key,
        "billing_orders": billing_orders,
        "employees": employees,
        "active_employee": active_emp,
        "vobiz_caller_id": vobiz_caller_id,
        "sarvam_key_masked": sarvam_key_masked,
        "vobiz_auth_id_masked": vobiz_auth_id_masked,
        "dialer_provider": dialer_provider,
    })
