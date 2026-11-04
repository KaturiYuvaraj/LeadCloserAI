"""
Knowledge Router - documents the AI employee answers from, and call analytics.

  GET    /api/employees/{id}/knowledge            list uploaded documents
  POST   /api/employees/{id}/knowledge            upload PDF / Word / Excel / CSV / TXT / MD
  DELETE /api/employees/{id}/knowledge/{index}    remove a document
  GET    /api/analytics/calls?days=30             call analytics from the voice engine

Live calls use the documents of the AI employee on the call (voice_agent/knowledge.py).
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from core.auth import get_request_account_id
from core.db import SessionLocal
from models import Call, Employee
from voice_agent.knowledge import ALLOWED_SUFFIXES, add_doc, delete_doc, extract_text, list_docs

router = APIRouter(tags=["knowledge"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _check_employee(emp_id: int, request: Request) -> None:
    """404 unless the AI employee belongs to the signed-in user's account."""
    account_id = get_request_account_id(request)
    session = SessionLocal()
    try:
        query = session.query(Employee.id).filter(Employee.id == emp_id)
        if account_id is not None:
            query = query.filter(Employee.account_id == account_id)
        found = query.first()
    finally:
        session.close()
    if not found:
        raise HTTPException(status_code=404, detail="Employee not found")


@router.get("/api/employees/{emp_id}/knowledge")
async def api_list_knowledge(emp_id: int, request: Request):
    _check_employee(emp_id, request)
    docs = list_docs(emp_id)
    if docs is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"documents": docs, "accepted": sorted(ALLOWED_SUFFIXES)}


@router.post("/api/employees/{emp_id}/knowledge")
async def api_upload_knowledge(emp_id: int, request: Request, file: UploadFile = File(...)):
    _check_employee(emp_id, request)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 15 MB.")
    try:
        text = extract_text(file.filename or "document.txt", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    saved = add_doc(emp_id, file.filename or "document", text)
    if saved is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"success": True, **saved}


@router.delete("/api/employees/{emp_id}/knowledge/{index}")
async def api_delete_knowledge(emp_id: int, index: int, request: Request):
    _check_employee(emp_id, request)
    if not delete_doc(emp_id, index):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True}


def call_analytics(days: int = 30, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Totals over recent calls: connection, outcomes, end reasons, languages, actions, reply speed."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    session = SessionLocal()
    try:
        query = session.query(Call).filter(Call.created_at >= since.replace(tzinfo=None))
        if account_id is not None:
            query = query.filter(Call.account_id == account_id)
        calls = query.all()
    finally:
        session.close()

    outcomes, end_reasons, languages, actions, signals = Counter(), Counter(), Counter(), Counter(), Counter()
    talk, gaps, interruptions, conversations = [], [], 0, 0
    for call in calls:
        outcomes[call.outcome or "unknown"] += 1
        data = (call.captured or {}).get("analytics") or {}
        end_reasons[data.get("end_reason") or call.ended_by or "unknown"] += 1
        for lang in data.get("languages") or []:
            languages[lang] += 1
        for action in data.get("actions") or []:
            actions[action.get("action", "?")] += 1
        for name, count in (data.get("signals") or {}).items():
            signals[name] += count
        interruptions += int(data.get("interruptions") or 0)
        if data.get("user_turns"):
            conversations += 1
            talk.append(call.talk_seconds or 0)
        if call.latency_avg_ms:
            gaps.append(float(call.latency_avg_ms))

    machines = sum(end_reasons[k] for k in ("voicemail", "ivr", "unreachable"))
    return {
        "days": days,
        "total_calls": len(calls),
        "conversations": conversations,
        "machine_answered": machines,
        "no_response": end_reasons["no_response"],
        "avg_talk_seconds": round(sum(talk) / len(talk), 1) if talk else 0,
        "avg_reply_gap_ms": round(sum(gaps) / len(gaps)) if gaps else None,
        "interruptions": interruptions,
        "outcomes": dict(outcomes.most_common()),
        "end_reasons": dict(end_reasons.most_common()),
        "languages": dict(languages.most_common()),
        "actions": dict(actions.most_common()),
        "caller_signals": dict(signals.most_common()),
    }


@router.get("/api/analytics/calls")
async def api_call_analytics(request: Request, days: int = 30):
    return call_analytics(days, get_request_account_id(request))
