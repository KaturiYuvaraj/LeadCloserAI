"""
AI Employees Router - Persona Management, Draft Generation & Lifecycle
"""
from typing import Dict, Any, Optional
from fastapi import Depends
from fastapi import APIRouter, HTTPException, Request
from core.auth import get_current_user, get_request_account_id, login_when_strict

from database import (
    get_all_ai_employees,
    get_active_ai_employee,
    get_ai_employee_by_id,
    create_ai_employee,
    update_ai_employee,
    set_active_ai_employee,
    delete_ai_employee,
)
from services.employee_builder import employee_builder

router = APIRouter(tags=["employees"], dependencies=[Depends(login_when_strict)])


def _own(emp_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    """The employee, only if it belongs to the signed-in company (28 Nov: any company's could be read,
    edited, approved, activated or deleted). Another company's employee answers 404, as if it didn't exist."""
    emp = get_ai_employee_by_id(emp_id, account_id=int(user["account_id"]))
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.get("/api/employees")
async def api_get_employees(request: Request):
    """List all configured and seeded AI sales employees."""
    acc_id = get_request_account_id(request)
    return {
        "employees": get_all_ai_employees(account_id=acc_id),
        "active_employee": get_active_ai_employee(account_id=acc_id)
    }


@router.post("/api/employees/generate")
async def api_generate_employee_draft(payload: Dict[str, Any]):
    """
    AI Assistant to generate a production-ready AI employee draft from a plain instruction.
    Status is strictly 'draft' and requires admin approval before activation.
    """
    instruction = payload.get("instruction", "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="User instruction is required.")

    preferred_language = payload.get("language")
    draft = await employee_builder.generate_draft_from_instruction(
        instruction=instruction,
        preferred_language=preferred_language
    )
    return {"success": True, "draft": draft}


@router.post("/api/employees")
async def api_create_employee(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new AI employee (draft or approved) in the signed-in company."""
    payload["account_id"] = int(user["account_id"])  # never from the request
    if not payload.get("name") or not payload.get("greeting"):
        raise HTTPException(status_code=400, detail="Name and greeting are required.")

    emp_id = create_ai_employee(payload)
    return {"success": True, "employee_id": emp_id, "message": "AI Employee created successfully."}


@router.get("/api/employees/{emp_id}")
async def api_get_employee(emp_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    return {"employee": _own(emp_id, user)}


@router.put("/api/employees/{emp_id}")
async def api_update_employee(emp_id: int, payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    _own(emp_id, user)
    payload.pop("account_id", None)  # an employee cannot be moved to another company
    success = update_ai_employee(emp_id, payload)
    return {"success": success, "employee": get_ai_employee_by_id(emp_id)}


@router.post("/api/employees/{emp_id}/approve")
async def api_approve_employee(emp_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    """Approve a draft employee so it can be activated in production."""
    _own(emp_id, user)

    update_ai_employee(emp_id, {"status": "approved"})
    return {"success": True, "employee": get_ai_employee_by_id(emp_id)}


@router.post("/api/employees/{emp_id}/activate")
async def api_activate_employee(emp_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    """Set an employee as the company's primary active caller for inbound/outbound sales."""
    emp = _own(emp_id, user)

    if emp.get("status") == "draft":
        raise HTTPException(status_code=400, detail="Draft employee must be reviewed and approved by an administrator before activation.")

    set_active_ai_employee(emp_id)
    return {
        "success": True,
        "message": f"AI Employee '{emp['name']}' is now actively deployed for all live calls.",
        "active_employee": get_ai_employee_by_id(emp_id)
    }


@router.delete("/api/employees/{emp_id}")
async def api_delete_employee(emp_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    emp = _own(emp_id, user)
    if emp.get("is_active"):
        raise HTTPException(status_code=400, detail="Cannot delete currently active employee. Activate another employee first.")

    delete_ai_employee(emp_id, account_id=int(user["account_id"]))
    return {"success": True, "message": "Employee deleted successfully."}



@router.post("/api/employees/{emp_id}/duplicate")
async def api_duplicate_employee(emp_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    """Duplicate one of the company's AI employees with a '(Copy)' suffix."""
    acc_id = int(user["account_id"])
    emp = _own(emp_id, user)

    clone_payload = {
        "account_id": acc_id,
        "name": f"{emp.get('name', 'AI Employee')} (Copy)",
        "role_title": emp.get("role_title", "Sales Specialist"),
        "primary_language": emp.get("primary_language", "te-IN"),
        "fallback_language": emp.get("fallback_language", "en-IN"),
        "voice_gender": emp.get("voice_gender", "female"),
        "speaker_id": emp.get("speaker_id", "meera"),
        "tone": emp.get("tone", "Professional, warm, helpful"),
        "system_prompt": emp.get("system_prompt", ""),
        "greeting": emp.get("greeting", ""),
        "offer_details": emp.get("offer_details", ""),
        "status": "draft",
        "is_active": False,
        "created_by": "cloned",
    }
    new_id = create_ai_employee(clone_payload)
    new_emp = get_ai_employee_by_id(new_id)
    return {
        "success": True,
        "employee_id": new_id,
        "employee": new_emp,
        "message": f"Successfully duplicated '{emp.get('name')}' as draft."
    }


@router.post("/api/employees/{emp_id}/test")
async def api_test_employee_voice(emp_id: int, payload: Optional[Dict[str, Any]] = None,
                                  user: Dict[str, Any] = Depends(get_current_user)):
    """
    Synthesize the employee's greeting or custom test phrase via Sarvam TTS
    and return base64-encoded audio for instant in-browser auditioning.
    """
    emp = _own(emp_id, user)

    text = (payload or {}).get("text") or emp.get("greeting") or "Hello, this is a voice test."
    lang = emp.get("primary_language", "te-IN")
    speaker = emp.get("speaker_id", "meera")

    try:
        from services.sarvam_service import sarvam_service
        audio_bytes = await sarvam_service.text_to_speech(text=text, language_code=lang, speaker=speaker)
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else None
        return {
            "success": True,
            "text": text,
            "language": lang,
            "speaker": speaker,
            "audio_base64": audio_b64,
            "mime_type": "audio/wav",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": text,
            "note": "TTS synthesis failed or mock audio fallback."
        }
