"""
Pages Router - HTML Dashboard View
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from core.web import templates
from database import (
    get_company_profile,
    get_all_leads,
    get_call_history,
    get_all_api_keys,
    get_primary_api_key,
    get_billing_orders,
    get_all_provider_settings,
    get_all_ai_employees,
    get_active_ai_employee,
)
from providers import registry

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
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

    employees = get_all_ai_employees()
    active_emp = get_active_ai_employee()
    return templates.TemplateResponse(request, "index.html", {
        "profile": profile,
        "leads": leads,
        "calls": calls,
        "api_keys": api_keys,
        "primary_key": primary_key,
        "billing_orders": billing_orders,
        "providers": providers_list,
        "employees": employees,
        "active_employee": active_emp
    })

