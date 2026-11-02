"""
AI Employees Router - Persona Management, Draft Generation & Lifecycle
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

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

router = APIRouter(tags=["employees"])


@router.get("/api/employees")
async def api_get_employees():
    """List all configured and seeded AI sales employees."""
    return {
        "employees": get_all_ai_employees(),
        "active_employee": get_active_ai_employee()
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
async def api_create_employee(payload: Dict[str, Any]):
    """Create a new AI employee (draft or approved)."""
    if not payload.get("name") or not payload.get("greeting"):
        raise HTTPException(status_code=400, detail="Name and greeting are required.")

    emp_id = create_ai_employee(payload)
    return {"success": True, "employee_id": emp_id, "message": "AI Employee created successfully."}


@router.get("/api/employees/{emp_id}")
async def api_get_employee(emp_id: int):
    emp = get_ai_employee_by_id(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"employee": emp}


@router.put("/api/employees/{emp_id}")
async def api_update_employee(emp_id: int, payload: Dict[str, Any]):
    emp = get_ai_employee_by_id(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    success = update_ai_employee(emp_id, payload)
    return {"success": success, "employee": get_ai_employee_by_id(emp_id)}


@router.post("/api/employees/{emp_id}/approve")
async def api_approve_employee(emp_id: int):
    """Approve a draft employee so it can be activated in production."""
    emp = get_ai_employee_by_id(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_ai_employee(emp_id, {"status": "approved"})
    return {"success": True, "employee": get_ai_employee_by_id(emp_id)}


@router.post("/api/employees/{emp_id}/activate")
async def api_activate_employee(emp_id: int):
    """Set an employee as the primary active caller for inbound/outbound sales."""
    emp = get_ai_employee_by_id(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if emp.get("status") == "draft":
        raise HTTPException(status_code=400, detail="Draft employee must be reviewed and approved by an administrator before activation.")

    set_active_ai_employee(emp_id)
    return {
        "success": True,
        "message": f"AI Employee '{emp['name']}' is now actively deployed for all live calls.",
        "active_employee": get_ai_employee_by_id(emp_id)
    }


@router.delete("/api/employees/{emp_id}")
async def api_delete_employee(emp_id: int):
    emp = get_ai_employee_by_id(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.get("is_active"):
        raise HTTPException(status_code=400, detail="Cannot delete currently active employee. Activate another employee first.")

    delete_ai_employee(emp_id)
    return {"success": True, "message": "Employee deleted successfully."}

