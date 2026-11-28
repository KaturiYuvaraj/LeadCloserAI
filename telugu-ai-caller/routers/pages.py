"""
Pages Router - Separate Landing Page (Homepage) and Dedicated CRM Dashboard
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from core.auth import get_optional_user, get_request_account_id, is_platform_admin
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
    get_phone_numbers,
)

router = APIRouter(tags=["pages"])


def _user_or_none(request: Request):
    """Pages send logged-out visitors to /login, also when AUTH_STRICT=true makes the lookup raise 401."""
    try:
        return get_optional_user(request)
    except HTTPException:
        return None


# The public homepage shows these sample AI employees. It never reads a customer's records: before 28 Nov it
# listed the AI employees stored in the database (prompts and all), so a company's private setup was public.
SHOWCASE_EMPLOYEES = [
    {"id": 1, "name": "Shreya - Real Estate Sales", "role": "Telugu property sales caller",
     "description": "Calls property enquiries, shares project details and books site visits.",
     "language": "te-IN", "voice_speaker": "pooja_te_conversation", "working_hours": "09:00 - 19:00",
     "status": "live", "is_active": True,
     "greeting": "నమస్కారం అండి! మీరు అడిగిన ఫ్లాట్ వివరాల కోసం కాల్ చేస్తున్నాను. ఇప్పుడు మాట్లాడవచ్చా?"},
    {"id": 2, "name": "Kavya - Clinic Appointments", "role": "Hindi patient appointment assistant",
     "description": "Confirms and reschedules appointments and answers common questions about the clinic.",
     "language": "hi-IN", "voice_speaker": "kavya_hi_conversational", "working_hours": "08:00 - 20:00",
     "status": "approved", "is_active": False,
     "greeting": "नमस्ते! मैं क्लिनिक से बात कर रही हूँ। आपकी कल की अपॉइंटमेंट कन्फर्म करने के लिए कॉल किया है।"},
    {"id": 3, "name": "Simran - Admissions Counsellor", "role": "English admissions caller",
     "description": "Follows up course enquiries, explains fees and batches, and books counselling sessions.",
     "language": "en-IN", "voice_speaker": "simran_en_sales", "working_hours": "10:00 - 19:00",
     "status": "approved", "is_active": False,
     "greeting": "Hello! This is Simran calling about the course you enquired about. Is this a good time to talk?"},
    {"id": 4, "name": "Priya - Order Follow-up", "role": "Telugu customer follow-up caller",
     "description": "Calls customers after an order to confirm delivery, collect feedback and offer repeat deals.",
     "language": "te-IN", "voice_speaker": "kavitha_te_conversation", "working_hours": "09:30 - 18:30",
     "status": "approved", "is_active": False,
     "greeting": "నమస్కారం అండి! మీ ఆర్డర్ డెలివరీ అయిందా అని కనుక్కోవడానికి కాల్ చేస్తున్నాను."},
]


@router.get("/", response_class=HTMLResponse)
async def serve_landing(request: Request):
    """Public homepage: sample AI employees only, never a customer's data."""
    return templates.TemplateResponse(request, "index.html", {
        "profile": {},
        "api_keys": [],
        "primary_key": None,
        "employees": SHOWCASE_EMPLOYEES,
        "active_employee": SHOWCASE_EMPLOYEES[0],
    })


@router.get("/set-password", response_class=HTMLResponse)
async def serve_set_password_page(request: Request):
    """
    Dedicated screen for users to replace their initial placeholder password.
    Redirects unauthenticated users to /login.
    """
    current_user = _user_or_none(request)
    if not current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login?next=/set-password", status_code=302)
    return templates.TemplateResponse(request, "set_password.html", {"current_user": current_user})


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
    current_user = _user_or_none(request)
    if not current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login?next=" + request.url.path, status_code=302)
    # every lookup is limited to the signed-in company (28 Nov: these were not, so a new customer saw
    # S P Associates' AI employees, API keys and orders)
    account_id = int(current_user["account_id"])
    profile = get_company_profile(account_id=account_id)
    leads = get_all_leads(account_id=account_id)
    calls = get_call_history(limit=20, account_id=account_id)
    outcome_summary = get_outcome_bucket_summary(account_id=account_id)
    api_keys = get_all_api_keys(account_id=account_id)
    primary_key = get_primary_api_key(account_id=account_id)
    billing_orders = get_billing_orders(account_id=account_id)
    employees = get_all_ai_employees(account_id=account_id)
    active_emp = get_active_ai_employee(account_id=account_id)
    phone_numbers = get_phone_numbers(account_id=account_id)

    import os
    from config import VOBIZ_CALLER_ID, SARVAM_API_KEY, DIALER_PROVIDER, VOBIZ_AUTH_ID
    vobiz_caller_id = os.getenv("VOBIZ_CALLER_ID", VOBIZ_CALLER_ID)
    sarvam_key = os.getenv("SARVAM_API_KEY", SARVAM_API_KEY)
    sarvam_key_masked = sarvam_key[:6] + "****" + sarvam_key[-4:] if len(sarvam_key) > 10 else "Active"
    vobiz_auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
    vobiz_auth_id_masked = vobiz_auth_id[:4] + "****" + vobiz_auth_id[-4:] if len(vobiz_auth_id) > 8 else "Active"
    dialer_provider = os.getenv("DIALER_PROVIDER", DIALER_PROVIDER)
    if not is_platform_admin(current_user):  # the platform's own provider accounts are for the platform owner only
        vobiz_caller_id, sarvam_key_masked, vobiz_auth_id_masked = "", "Managed by GeniusBot", "Managed by GeniusBot"

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
        "phone_numbers": phone_numbers,
        "vobiz_caller_id": vobiz_caller_id,
        "sarvam_key_masked": sarvam_key_masked,
        "vobiz_auth_id_masked": vobiz_auth_id_masked,
        "dialer_provider": dialer_provider,
    })


# ---------------------------------------------------------------- homepage voice demo
# The homepage plays sample voices. /api/tts/test (any text) now needs a login, because anyone could make it
# read unlimited text on our Sarvam account (20 Nov). This public route only voices the homepage's fixed
# samples and the AI employees' saved greetings, with the voice the page asks for, and keeps each result,
# so a sample costs Sarvam once.
HOMEPAGE_DEMO_TEXTS = {
    "नमस्ते! मैं एस पी एसोसिएट्स से बात कर रहा हूँ। क्या आप अपने व्यापार के लिए कस्टम सॉफ़्टवेयर समाधान ढूंढ रहे हैं?",
    "Hello! This is Simran from S P Associates. We specialize in custom software development and AI automation.",
    "నమస్కారం అండి! నేను ఎస్ పి అసోసియేట్స్ నుండి మాట్లాడుతున్నాను. మీ వ్యాపారం కోసం అధునాతన సాఫ్ట్‌వేర్ సేవల గురించి చర్చించవచ్చా?",
    "నమస్కారం అండి! నేను ఎస్ పి అసోసియేట్స్ నుండి మాట్లాడుతున్నాను.",
}
_demo_audio: dict = {}


def demo_text_allowed(text: str) -> bool:
    return text in HOMEPAGE_DEMO_TEXTS or any(e["greeting"] == text for e in SHOWCASE_EMPLOYEES)


@router.post("/api/tts/demo")
async def homepage_voice_demo(payload: dict):
    from fastapi import Response
    from voice_agent.language import VOICES
    from services.sarvam_service import sarvam_client
    text = str(payload.get("text") or "").strip()
    speaker = str(payload.get("speaker") or "")
    allowed_speakers = set(VOICES.values()) | {"kavitha_te_conversation", "aditya_hi_sales", "simran_en_sales"}
    if not text or len(text) > 400 or not demo_text_allowed(text) or speaker not in allowed_speakers:
        raise HTTPException(status_code=403, detail="Only the homepage samples can be played.")
    key = (speaker, text)
    if key not in _demo_audio:
        if len(_demo_audio) >= 50:
            _demo_audio.clear()
        _demo_audio[key] = await sarvam_client.text_to_speech(text=text, speaker=speaker)
    return Response(content=_demo_audio[key], media_type="audio/wav")
