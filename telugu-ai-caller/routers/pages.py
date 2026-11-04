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
    Contains the 3-column Calling Station, Executive Dashboard, Leads Table,
    Autonomous Campaigns Manager, Automations, and Analytics.
    """
    current_user = get_optional_user(request)
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
        "active_employee": active_emp
    })
