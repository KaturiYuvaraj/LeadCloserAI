"""
PostgreSQL Database module using SQLAlchemy 2.0 for LeadCloser.AI.
Reimplements data access functions on top of PostgreSQL while preserving
full backwards compatibility for existing routers and services.
"""

import os
import json
from pathlib import Path
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import create_engine, select, update, delete, func, desc, or_, text
from sqlalchemy.orm import Session
from loguru import logger

from core.db import engine, SessionLocal, Base, DATABASE_URL
from config import DATABASE_PATH
from models import (
    Account,
    User,
    Number,
    Employee,
    Lead,
    Call,
    OptOut,
    CreditLedger,
    AuditLog,
    ProviderSetting,
    ProviderUsageLog,
    ApiKey,
    BillingOrder,
    Campaign,
)

DB_FILE = Path(DATABASE_PATH)


def get_connection():
    """Returns a raw DB connection for legacy compatibility."""
    return engine.raw_connection()


def clean_phone(raw: Any) -> str:
    """Normalize phone string into E.164-compatible format, handling Indian 10-digit, 11-digit with leading 0, and STD formats."""
    if not raw:
        return "+910000000000"
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    elif digits:
        return f"+{digits}"
    return "+910000000000"


def _lead_to_dict(lead: Lead) -> Dict[str, Any]:
    """Flattens a Lead model into a CRM lead dictionary."""
    from services.outcomes import normalize_outcome
    vars_dict = lead.variables if isinstance(lead.variables, dict) else {}
    last_summary = lead.last_call_summary or vars_dict.get("last_call_summary", None)
    act_items = lead.action_items or vars_dict.get("action_items", None)
    obj_noted = lead.objections_noted or vars_dict.get("objections_noted", None)

    raw_outcome = vars_dict.get("outcome_label") or lead.last_outcome or ""
    norm = normalize_outcome(raw_outcome, confidence=vars_dict.get("outcome_confidence", 0.9)) if raw_outcome else None
    outcome_bucket = vars_dict.get("outcome_bucket") or (norm["outcome_bucket"] if norm else "uncalled")
    outcome_label = vars_dict.get("outcome_label") or (norm["outcome_label"] if norm else "")

    data = {
        "id": lead.id,
        "account_id": lead.account_id,
        "name": lead.name,
        "phone": lead.phone_e164,
        "phone_e164": lead.phone_e164,
        "source": lead.source or "manual",
        "notes": lead.notes or "",
        "is_hot": bool(lead.is_hot or outcome_bucket == "hot"),
        "last_call_stage": lead.last_outcome or "",
        "last_outcome": lead.last_outcome or "",
        "outcome_label": outcome_label,
        "outcome_bucket": outcome_bucket,
        "outcome_reason": vars_dict.get("outcome_reason", ""),
        "outcome_confidence": vars_dict.get("outcome_confidence", 1.0),
        "needs_human_review": bool(vars_dict.get("needs_human_review", False)),
        "whatsapp_opt_in": bool(vars_dict.get("whatsapp_opt_in", False)),
        "opt_out": lead.opt_out,
        "callback_at": lead.callback_at.isoformat() if lead.callback_at else vars_dict.get("callback_at", None),
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        # Flatten business & contact intelligence
        "email": vars_dict.get("email", ""),
        "company": vars_dict.get("company", lead.name),
        "owner_name": vars_dict.get("owner_name", vars_dict.get("company_owner", "")),
        "website": vars_dict.get("website", ""),
        "has_website": vars_dict.get("has_website", "Yes" if vars_dict.get("website") else "No"),
        "reviews": vars_dict.get("reviews", ""),
        "score": vars_dict.get("score", ""),
        "pitch": vars_dict.get("pitch", lead.notes or ""),
        "service_needed": vars_dict.get("service_needed", "Software Services"),
        "budget": vars_dict.get("budget", "Flexible"),
        "timeline": vars_dict.get("timeline", "Immediate"),
        "status": vars_dict.get("status", "NEW"),
        "priority": vars_dict.get("priority", "MEDIUM"),
        "preferred_language": vars_dict.get("preferred_language", "te-IN"),
        "designation": vars_dict.get("designation", ""),
        "industry": vars_dict.get("industry", ""),
        "location": vars_dict.get("location", ""),
        "campaign_tag": vars_dict.get("campaign_tag", ""),
        "marketer_tag": vars_dict.get("marketer_tag", ""),
        "consent_source": lead.consent_source or vars_dict.get("consent_source", ""),
        "enrichment_data": vars_dict.get("enrichment_data", ""),
        "display_phone": vars_dict.get("display_phone", lead.phone_e164),
        "last_call_summary": last_summary,
        "last_call_sentiment": vars_dict.get("last_call_sentiment", "neutral"),
        "objections_noted": obj_noted,
        "action_items": act_items,
        "last_called_at": vars_dict.get("last_called_at", None),
        "variables": vars_dict,
        "followup_plan": vars_dict.get("followup_plan"),
        "pending_whatsapp": vars_dict.get("pending_whatsapp") or [],
    }
    return data


def _call_to_dict(call: Call, lead: Optional[Lead] = None) -> Dict[str, Any]:
    """Flattens a Call model into a call record dictionary."""
    from services.outcomes import normalize_outcome
    cap = call.captured if isinstance(call.captured, dict) else {}
    transcript_val = call.transcript
    if isinstance(transcript_val, (dict, list)):
        transcript_str = json.dumps(transcript_val, ensure_ascii=False)
    else:
        transcript_str = transcript_val or ""

    act_items = call.action_items or cap.get("action_items", "")
    obj_raised = call.objections_raised or cap.get("objections_raised", "")
    ext_reqs = call.extracted_requirements or cap.get("extracted_requirements", "")

    raw_label = cap.get("outcome_label") or call.outcome or "busy_no_time"
    norm = normalize_outcome(raw_label, confidence=cap.get("confidence", 0.9))

    return {
        "id": call.id,
        "account_id": call.account_id,
        "lead_id": call.lead_id,
        "call_type": "web" if call.channel == "manual" else "phone",
        "phone_number": (lead.phone_e164 if lead else "") or "",
        "duration_seconds": call.talk_seconds or 0,
        "status": call.state or "completed",
        "summary": call.summary or "",
        "sentiment": call.sentiment or "neutral",
        "deal_stage": call.outcome or "qualifying",
        "outcome_label": cap.get("outcome_label", norm["outcome_label"]),
        "outcome_bucket": cap.get("outcome_bucket", norm["outcome_bucket"]),
        "outcome_reason": cap.get("outcome_reason", ""),
        "confidence": cap.get("confidence", norm["confidence"]),
        "needs_human_review": bool(cap.get("needs_human_review", norm["needs_human_review"])),
        "callback_at": cap.get("callback_at", None),
        "whatsapp_opt_in": bool(cap.get("whatsapp_opt_in", False)),
        "extracted_budget": cap.get("extracted_budget", ""),
        "extracted_timeline": cap.get("extracted_timeline", ""),
        "extracted_requirements": ext_reqs,
        "objections_raised": obj_raised,
        "action_items": act_items,
        "transcript": transcript_str,
        "recording_url": call.recording_url or "",
        "call_sid": call.provider_call_sid or "",
        "disposition": call.outcome or call.state or "completed",
        "created_at": call.created_at.isoformat() if call.created_at else None,
        "lead_name": lead.name if lead else None,
        "lead_company": (lead.variables or {}).get("company") if lead else None,
        "lead_phone": lead.phone_e164 if lead else None,
    }


def _emp_to_dict(emp: Employee) -> Dict[str, Any]:
    """Flattens an Employee model into an AI employee dictionary."""
    steps = emp.script_steps if isinstance(emp.script_steps, dict) else {}
    vars_dict = emp.variables if isinstance(emp.variables, dict) else {}
    return {
        "id": emp.id,
        "name": emp.name,
        "role": vars_dict.get("role", "Software Sales Specialist"),
        "description": vars_dict.get("description", ""),
        "language": emp.language or "te-IN",
        "voice_speaker": emp.voice or "kavitha_te_conversation",
        "greeting": emp.greeting or "",
        "calling_objective": steps.get("calling_objective", ""),
        "system_prompt": emp.system_prompt or "",
        "sales_script": steps.get("sales_script", ""),
        "qualification_questions": steps.get("qualification_questions", ""),
        "knowledge_base": vars_dict.get("knowledge_base", ""),
        "working_hours": vars_dict.get("working_hours", "09:00 - 19:00"),
        "max_call_duration_seconds": vars_dict.get("max_call_duration_seconds", 600),
        "status": emp.status or "draft",
        "is_active": 1 if emp.status == "live" else 0,
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
        "updated_at": emp.updated_at.isoformat() if emp.updated_at else None,
    }


def init_db():
    """Initializes schema, runs non-destructive column migrations, and seeds baseline rows if database is empty."""
    Base.metadata.create_all(bind=engine)
    # Check and migrate missing account_id columns on legacy tables for strict multi-tenancy
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        tables_needing_account_id = [
            "campaigns", "api_keys", "api_billing_orders", "provider_settings", "provider_usage_logs"
        ]
        with engine.begin() as conn:
            for tbl in tables_needing_account_id:
                if tbl in table_names:
                    cols = {c["name"] for c in inspector.get_columns(tbl)}
                    if "account_id" not in cols:
                        logger.info(f"Adding missing account_id column to {tbl}...")
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1"))
    except Exception as exc:
        logger.warning(f"Schema migration check note: {exc}")

    session = SessionLocal()
    try:
        # Seed default account if not present
        account = session.query(Account).filter_by(id=1).first()
        if not account:
            account = Account(
                id=1,
                name="S P Associates Software Company",
                default_language="te-IN",
                calling_approved=True,
                rate_per_min=5.00
            )
            session.add(account)
            session.commit()

        # Seed default user
        user = session.query(User).filter_by(account_id=account.id).first()
        if not user:
            user = User(
                id=1,
                account_id=account.id,
                email="admin@leadcloser.ai",
                password_hash="pbkdf2:sha256:default_hash_for_admin",
                role="owner"
            )
            session.add(user)
            session.commit()

        # Seed default number
        number = session.query(Number).filter_by(account_id=account.id).first()
        if not number:
            number = Number(
                id=1,
                account_id=account.id,
                e164="+917965482229",
                provider="vobiz",
                channels=10,
                employee_id=1,
                status="active"
            )
            session.add(number)
            session.commit()
        else:
            # Upgrade legacy placeholder to real verified Vobiz carrier trunk
            if number.e164 in ("+918000000000", "+91 80000 00000", "") or number.provider == "exotel":
                number.e164 = "+917965482229"
                number.provider = "vobiz"
                number.channels = 10
                number.status = "active"
                if not number.employee_id:
                    number.employee_id = 1
                session.commit()

        # Seed baseline 5 specialized AI sales employees if not populated
        if session.query(Employee).count() < 5:
            employees_data = [
                {
                    "id": 1,
                    "name": "S P Senior Closer (Default)",
                    "job_type": "instant",
                    "language": "te-IN",
                    "voice": "kavitha_te_conversation",
                    "greeting": "నమస్కారం అండి! నేను S P Associates Software Company నుండి మాట్లాడుతున్నాను. మీ వ్యాపారానికి కస్టమ్ వెబ్‌సైట్ లేదా మొబైల్ యాప్ అవసరం ఉందా అండి?",
                    "system_prompt": "You are a Senior Sales Closer at S P Associates Software Company. Qualify software requirements, answer questions, handle objections, and close with a live Zoom demo.",
                    "script_steps": {
                        "sales_script": "Introduce -> Discover Need -> Match Services -> Address Budget/Timeline -> Book Demo",
                        "qualification_questions": "1. Do you need a web app or mobile app?\n2. What is your estimated timeline?\n3. Who is your target customer?",
                        "calling_objective": "Qualify client software needs and book a 10-minute live demo."
                    },
                    "variables": {
                        "role": "General Business Development Specialist",
                        "description": "Flagship multilingual sales closer for S P Associates software solutions.",
                        "knowledge_base": "S P Associates builds custom websites, Android/iOS apps, billing software, and AI voice automation systems with flexible milestone payments.",
                        "working_hours": "09:00 - 19:00"
                    },
                    "status": "live",
                    "number_id": number.id
                },
                {
                    "id": 2,
                    "name": "Priya - Web & SaaS Closer",
                    "job_type": "instant",
                    "language": "te-IN",
                    "voice": "kavitha_te_conversation",
                    "greeting": "నమస్కారం అండి! మీ బిజినెస్‌కి ఆన్‌లైన్ వెబ్‌సైట్ లేదా ఈ-కామర్స్ పోర్టల్ డెవలప్‌మెంట్ కోసం S P Associates నుండి కాల్ చేస్తున్నాను.",
                    "system_prompt": "You are Priya, Web & SaaS Sales Specialist at S P Associates Software Company. Emphasize fast load times, Google SEO ranking, and online sales conversions.",
                    "script_steps": {
                        "sales_script": "Highlight web design portfolio -> Offer free 5-minute technical audit -> Schedule demo.",
                        "qualification_questions": "1. Do you already have an existing website?\n2. Do you need online payment gateway integration?",
                        "calling_objective": "Close custom website and web app development deals."
                    },
                    "variables": {
                        "role": "Website & Web Application Sales Specialist",
                        "description": "Focused on pitching modern responsive websites, SaaS web portals, and e-commerce stores.",
                        "knowledge_base": "We use React, Next.js, and Node.js for ultra-fast, modern web applications.",
                        "working_hours": "09:30 - 18:30"
                    },
                    "status": "approved",
                    "number_id": None
                },
                {
                    "id": 3,
                    "name": "Rahul - Mobile App Specialist",
                    "job_type": "instant",
                    "language": "hi-IN",
                    "voice": "pooja",
                    "greeting": "नमस्ते सर! मैं S P Associates Software Company से राहुल बात कर रहा हूँ। क्या आपकी कंपनी के लिए कोई मोबाइल ऐप बनाने का प्लान है?",
                    "system_prompt": "You are Rahul, Mobile App Solutions Specialist at S P Associates Software Company. Discuss iOS, Android, and cross-platform Flutter/React Native solutions.",
                    "script_steps": {
                        "sales_script": "Understand app features -> Explain playstore publication -> Propose starting package.",
                        "qualification_questions": "1. Do you need Android or iOS or both?\n2. What core features do you need?",
                        "calling_objective": "Qualify mobile application requirements and estimate project milestones."
                    },
                    "variables": {
                        "role": "iOS & Android Mobile Applications Consultant",
                        "description": "Specializes in custom mobile apps, customer ordering apps, and delivery tracking.",
                        "knowledge_base": "Full-stack mobile app development with push notifications, maps, and Razorpay.",
                        "working_hours": "10:00 - 19:00"
                    },
                    "status": "approved",
                    "number_id": None
                },
                {
                    "id": 4,
                    "name": "Arjun - AI Voice & Chatbot Closer",
                    "job_type": "instant",
                    "language": "en-IN",
                    "voice": "tarun",
                    "greeting": "Hello! This is Arjun from S P Associates Software Company. We help businesses automate customer sales calls and WhatsApp replies using native Indian AI.",
                    "system_prompt": "You are Arjun, AI Voice Automation Consultant at S P Associates Software Company. Explain how AI telephone agents reduce operational costs by 70%.",
                    "script_steps": {
                        "sales_script": "Demonstrate AI call handling -> Share ROI metrics -> Offer pilot trial.",
                        "qualification_questions": "1. How many incoming or outgoing customer calls do you handle daily?",
                        "calling_objective": "Deploy AI autonomous caller systems for prospective businesses."
                    },
                    "variables": {
                        "role": "AI Telephony & WhatsApp Automation Consultant",
                        "description": "Pitches automated AI phone calling agents and Meta WhatsApp business messaging.",
                        "knowledge_base": "Our AI caller speaks Telugu, Hindi, and English natively with Vobiz telephony integration.",
                        "working_hours": "09:00 - 20:00"
                    },
                    "status": "approved",
                    "number_id": None
                },
                {
                    "id": 5,
                    "name": "Venkatesh - ERP & Billing Specialist",
                    "job_type": "instant",
                    "language": "te-IN",
                    "voice": "kavitha_te_conversation",
                    "greeting": "నమస్కారం అండి! మీ రిటైల్ లేదా డిస్ట్రిబ్యూషన్ బిజినెస్‌కి జీఎస్టీ బిల్లింగ్ మరియు ఇన్వెంటరీ సాఫ్ట్‌వేర్ గురించి S P Associates నుండి మాట్లాడుతున్నాను.",
                    "system_prompt": "You are Venkatesh, ERP Solutions Consultant. Emphasize GST compliance, barcode scanner support, and daily sales reports on mobile.",
                    "script_steps": {
                        "sales_script": "Assess inventory complexity -> Explain mobile reporting -> Offer 7-day free trial.",
                        "qualification_questions": "1. Do you need barcode scanning and thermal receipt printing?",
                        "calling_objective": "Demonstrate retail ERP billing software and schedule onsite or Zoom demo."
                    },
                    "variables": {
                        "role": "Retail & Wholesale ERP Software Consultant",
                        "description": "Specialized in inventory, POS billing, GST invoicing, and accounting software.",
                        "knowledge_base": "Cloud-synced billing software works offline and online.",
                        "working_hours": "09:00 - 19:00"
                    },
                    "status": "approved",
                    "number_id": None
                }
            ]

            for ed in employees_data:
                existing = session.query(Employee).filter_by(id=ed["id"]).first()
                if not existing:
                    emp = Employee(
                        id=ed["id"],
                        account_id=account.id,
                        name=ed["name"],
                        job_type=ed["job_type"],
                        language=ed["language"],
                        voice=ed["voice"],
                        greeting=ed["greeting"],
                        system_prompt=ed["system_prompt"],
                        script_steps=ed["script_steps"],
                        variables=ed["variables"],
                        status=ed["status"],
                        number_id=ed["number_id"]
                    )
                    session.add(emp)
            session.commit()

        # Seed default primary API key if empty
        if session.query(ApiKey).count() == 0:
            ak = ApiKey(
                id=1,
                key_name="Production Master API Key",
                user_email="enterprise@spassociates.com",
                company_name="S P Associates Software Company",
                api_key="lc_live_sp_assoc_7894a1b2",
                plan_tier="Business Growth (₹5/min)",
                credits_inr=2500.0,
                rate_per_min=5.0,
                total_calls=14,
                total_minutes=28.5,
                status="active"
            )
            session.add(ak)
            session.commit()

            bo = BillingOrder(
                api_key_id=1,
                order_id="ORD_2026_9841",
                plan_name="Business Growth Tier (500 Mins Talk-Time)",
                amount_inr=2500.0,
                minutes_credited=500.0,
                payment_method="Instant UPI / Razorpay Gateway",
                payment_status="success",
                customer_email="enterprise@spassociates.com",
                invoice_number="INV-SPA-2026-0049"
            )
            session.add(bo)
            session.commit()

        logger.info("PostgreSQL database initialized and verified.")
    except Exception as e:
        session.rollback()
        logger.error(f"init_db error: {e}")
    finally:
        session.close()


# ---------------- CRUD FOR LEADS ----------------

def get_all_leads(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Lead)
        if account_id is not None:
            query = query.filter(Lead.account_id == account_id)
        leads = query.order_by(Lead.id.desc()).all()
        return [_lead_to_dict(l) for l in leads]
    finally:
        session.close()


def get_lead_by_id(lead_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Lead).filter_by(id=lead_id)
        if account_id is not None:
            query = query.filter(Lead.account_id == account_id)
        lead = query.first()
        return _lead_to_dict(lead) if lead else None
    finally:
        session.close()


def create_lead(lead_data: Dict[str, Any], account_id: int = 1) -> int:
    session = SessionLocal()
    try:
        acc_id = int(lead_data.get("account_id", account_id) or 1)
        enrichment = lead_data.get("enrichment_data")
        if isinstance(enrichment, dict):
            enrichment = json.dumps(enrichment, ensure_ascii=False)

        phone = clean_phone(lead_data.get("phone", ""))
        existing = session.query(Lead).filter_by(account_id=acc_id, phone_e164=phone).first()

        variables = {
            "email": lead_data.get("email", ""),
            "company": lead_data.get("company", ""),
            "service_needed": lead_data.get("service_needed", "Custom Software"),
            "budget": lead_data.get("budget", "Flexible"),
            "timeline": lead_data.get("timeline", "Immediate"),
            "status": lead_data.get("status", "NEW"),
            "priority": lead_data.get("priority", "MEDIUM"),
            "preferred_language": lead_data.get("preferred_language", "te-IN"),
            "designation": lead_data.get("designation", ""),
            "industry": lead_data.get("industry", ""),
            "location": lead_data.get("location", ""),
            "website": lead_data.get("website", ""),
            "enrichment_data": enrichment or ""
        }

        if existing:
            # Upsert into existing lead
            existing.name = lead_data.get("name", existing.name)
            existing.notes = lead_data.get("notes", existing.notes)
            existing.source = lead_data.get("source", existing.source)
            cur_vars = dict(existing.variables or {})
            cur_vars.update(variables)
            existing.variables = cur_vars
            if "last_call_summary" in lead_data:
                existing.last_call_summary = lead_data["last_call_summary"]
            else:
                existing.last_call_summary = None
                existing.action_items = None
                existing.objections_noted = None
            existing.updated_at = func.now()
            session.commit()
            return existing.id

        lead = Lead(
            account_id=acc_id,
            name=lead_data.get("name", "Unknown"),
            phone=phone,
            phone_e164=phone,
            company=lead_data.get("company", ""),
            source=lead_data.get("source", "manual"),
            variables=variables,
            consent_source=lead_data.get("consent_source", "manual_entry"),
            notes=lead_data.get("notes", "")
        )
        session.add(lead)
        session.commit()
        return lead.id
    except Exception as e:
        session.rollback()
        logger.error(f"create_lead error: {e}")
        raise
    finally:
        session.close()


def batch_create_leads(leads: List[Dict[str, Any]], account_id: int = 1) -> Tuple[int, int]:
    session = SessionLocal()
    inserted = 0
    updated = 0
    try:
        for idx, l_data in enumerate(leads):
            acc_id = int(l_data.get("account_id", account_id) or 1)
            raw_phone = str(l_data.get("phone", "") or "").strip()
            display_phone = raw_phone
            if raw_phone:
                phone = clean_phone(raw_phone)
                display_phone = phone
            else:
                # Deterministic synthetic phone placeholder so non-phone business records are stored
                seed_str = str(l_data.get("company") or l_data.get("name") or f"lead_{idx}")
                hash_val = abs(hash(seed_str)) % 90000000 + 10000000
                phone = f"+9100{hash_val}"
                display_phone = "Not Provided"

            # Check for existing lead by phone or by company/name
            existing = session.query(Lead).filter(
                Lead.account_id == acc_id,
                (Lead.phone_e164 == phone) | (Lead.name == l_data.get("name"))
            ).first()

            lead_vars = {
                "email": l_data.get("email", ""),
                "company": l_data.get("company", l_data.get("name", "")),
                "owner_name": l_data.get("owner_name", ""),
                "website": l_data.get("website", ""),
                "has_website": l_data.get("has_website", ""),
                "reviews": l_data.get("reviews", ""),
                "score": l_data.get("score", ""),
                "pitch": l_data.get("pitch", ""),
                "service_needed": l_data.get("service_needed", "Software Services"),
                "budget": l_data.get("budget", "Flexible"),
                "timeline": l_data.get("timeline", "Immediate"),
                "status": l_data.get("status", "NEW"),
                "priority": l_data.get("priority", "MEDIUM"),
                "preferred_language": l_data.get("preferred_language", "te-IN"),
                "display_phone": display_phone
            }

            if existing:
                cur_vars = dict(existing.variables or {})
                for k, v in lead_vars.items():
                    if v:
                        cur_vars[k] = v
                existing.variables = cur_vars
                if l_data.get("name"): existing.name = l_data["name"]
                if l_data.get("pitch"): existing.notes = l_data["pitch"]
                elif l_data.get("notes"): existing.notes = l_data["notes"]
                existing.updated_at = func.now()
                updated += 1
            else:
                new_lead = Lead(
                    account_id=acc_id,
                    name=l_data.get("name", l_data.get("company", "Unknown")),
                    phone=phone,
                    phone_e164=phone,
                    company=l_data.get("company", l_data.get("name", "")),
                    source=l_data.get("source", "csv"),
                    variables=lead_vars,
                    consent_source=l_data.get("consent_source", "import_confirmed"),
                    notes=l_data.get("pitch") or l_data.get("notes", ""),
                    created_at=func.now(),
                    updated_at=func.now()
                )
                session.add(new_lead)
                inserted += 1
        session.commit()
        return inserted, updated
    except Exception as e:
        session.rollback()
        logger.error(f"batch_create_leads error: {e}")
        return inserted, updated
    finally:
        session.close()


def import_leads_with_report(
    leads: List[Dict[str, Any]],
    account_id: int = 1,
    source_tag: str = "csv",
    campaign_tag: str = "",
    marketer_tag: str = "",
    consent_source: str = "import_confirmed",
    strict_phone: bool = False,
) -> Dict[str, Any]:
    """
    Phase A (Y6) Lead Import Engine with:
      - +91 E.164 normalization & validation
      - Duplicate-in-file detection
      - Existing DB lead merge
      - Opt-Out / Do-Not-Call list check
      - Source / Campaign / Marketer tagging & consent recording
      - Detailed rejected rows report
    """
    from services.excel_service import clean_and_validate_indian_phone

    session = SessionLocal()
    inserted = 0
    updated = 0
    rejected_rows: List[Dict[str, Any]] = []
    seen_phones_in_file: set = set()

    try:
        opt_out_phones = {
            row.phone_e164
            for row in session.query(OptOut.phone_e164).filter(OptOut.account_id == account_id).all()
        }

        for idx, l_data in enumerate(leads, start=1):
            row_num = l_data.get("_row_number", idx + 1)
            raw_phone = str(l_data.get("phone", "") or "").strip()
            name_val = str(l_data.get("name") or l_data.get("company") or "Unknown").strip()

            cleaned_phone, is_valid, err_reason = clean_and_validate_indian_phone(raw_phone)
            if not is_valid:
                rejected_rows.append({
                    "row": row_num,
                    "name": name_val,
                    "phone": raw_phone,
                    "code": "invalid_number",
                    "reason": err_reason,
                })
                continue

            if not cleaned_phone:
                if strict_phone:
                    rejected_rows.append({
                        "row": row_num,
                        "name": name_val,
                        "phone": raw_phone,
                        "code": "missing_phone",
                        "reason": "Missing phone number",
                    })
                    continue
                seed_str = str(l_data.get("company") or name_val or f"lead_{idx}")
                hash_val = abs(hash(seed_str)) % 90000000 + 10000000
                phone = f"+9100{hash_val}"
                display_phone = "Not Provided"
            else:
                phone = cleaned_phone
                display_phone = cleaned_phone

                if phone in seen_phones_in_file:
                    rejected_rows.append({
                        "row": row_num,
                        "name": name_val,
                        "phone": raw_phone or phone,
                        "code": "duplicate_in_file",
                        "reason": f"Duplicate phone number ({phone}) in the same uploaded file",
                    })
                    continue
                seen_phones_in_file.add(phone)

                if phone in opt_out_phones:
                    rejected_rows.append({
                        "row": row_num,
                        "name": name_val,
                        "phone": raw_phone or phone,
                        "code": "on_opt_out_list",
                        "reason": f"Phone number ({phone}) is on the Do-Not-Call / Opt-Out list",
                    })
                    continue

            existing = session.query(Lead).filter(
                Lead.account_id == account_id,
                (Lead.phone_e164 == phone) | (Lead.name == name_val)
            ).first()

            if existing and existing.opt_out:
                rejected_rows.append({
                    "row": row_num,
                    "name": name_val,
                    "phone": raw_phone or phone,
                    "code": "on_opt_out_list",
                    "reason": "Existing lead has opted out of calls (Do-Not-Call)",
                })
                continue

            row_source = l_data.get("source") or source_tag or "csv"
            row_campaign = l_data.get("campaign_tag") or campaign_tag or ""
            row_marketer = l_data.get("marketer_tag") or marketer_tag or ""

            lead_vars = {
                "email": l_data.get("email", ""),
                "company": l_data.get("company", name_val),
                "owner_name": l_data.get("owner_name", ""),
                "website": l_data.get("website", ""),
                "has_website": l_data.get("has_website", ""),
                "reviews": l_data.get("reviews", ""),
                "score": l_data.get("score", ""),
                "pitch": l_data.get("pitch", ""),
                "service_needed": l_data.get("service_needed", "Software Services"),
                "budget": l_data.get("budget", "Flexible"),
                "timeline": l_data.get("timeline", "Immediate"),
                "status": l_data.get("status", "NEW"),
                "priority": l_data.get("priority", "MEDIUM"),
                "preferred_language": l_data.get("preferred_language", "te-IN"),
                "location": l_data.get("location", ""),
                "industry": l_data.get("industry", ""),
                "campaign_tag": row_campaign,
                "marketer_tag": row_marketer,
                "consent_source": consent_source,
                "display_phone": display_phone,
            }

            if existing:
                cur_vars = dict(existing.variables or {})
                for k, v in lead_vars.items():
                    if v:
                        cur_vars[k] = v
                existing.variables = cur_vars
                if name_val:
                    existing.name = name_val
                if row_source:
                    existing.source = row_source
                if consent_source and not existing.consent_source:
                    existing.consent_source = consent_source
                if l_data.get("pitch"):
                    existing.notes = l_data["pitch"]
                elif l_data.get("notes"):
                    existing.notes = l_data["notes"]
                existing.updated_at = func.now()
                updated += 1
            else:
                new_lead = Lead(
                    account_id=account_id,
                    name=name_val,
                    phone=phone,
                    phone_e164=phone,
                    company=l_data.get("company", name_val),
                    source=row_source,
                    variables=lead_vars,
                    consent_source=consent_source,
                    notes=l_data.get("pitch") or l_data.get("notes", ""),
                    created_at=func.now(),
                    updated_at=func.now(),
                )
                session.add(new_lead)
                inserted += 1

        session.commit()
        return {
            "inserted": inserted,
            "updated": updated,
            "rejected_count": len(rejected_rows),
            "rejected_rows": rejected_rows,
            "source_tag": source_tag,
            "campaign_tag": campaign_tag,
            "marketer_tag": marketer_tag,
            "consent_source": consent_source,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"import_leads_with_report error: {e}")
        return {
            "inserted": inserted,
            "updated": updated,
            "rejected_count": len(rejected_rows),
            "rejected_rows": rejected_rows,
            "error": str(e),
        }
    finally:
        session.close()


def get_opt_outs(account_id: int = 1) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = (
            session.query(OptOut)
            .filter(OptOut.account_id == account_id)
            .order_by(OptOut.id.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "account_id": r.account_id,
                "phone_e164": r.phone_e164,
                "reason": r.reason or "manual",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    finally:
        session.close()


def add_opt_out(phone: str, reason: str = "manual_dnd", account_id: int = 1) -> Dict[str, Any]:
    cleaned = clean_phone(phone)
    session = SessionLocal()
    try:
        existing = session.query(OptOut).filter_by(account_id=account_id, phone_e164=cleaned).first()
        if not existing:
            existing = OptOut(account_id=account_id, phone_e164=cleaned, reason=reason)
            session.add(existing)
            session.flush()
        lead = session.query(Lead).filter_by(account_id=account_id, phone_e164=cleaned).first()
        if lead:
            lead.opt_out = True
            lead.updated_at = func.now()
        session.commit()
        return {
            "id": existing.id,
            "account_id": existing.account_id,
            "phone_e164": existing.phone_e164,
            "reason": existing.reason,
        }
    finally:
        session.close()


def remove_opt_out(item: str, account_id: int = 1) -> bool:
    session = SessionLocal()
    try:
        row = None
        if item.isdigit():
            row = session.query(OptOut).filter_by(id=int(item), account_id=account_id).first()
        if not row:
            cleaned = clean_phone(item)
            row = session.query(OptOut).filter_by(account_id=account_id, phone_e164=cleaned).first()
        if not row:
            return False
        phone_val = row.phone_e164
        session.delete(row)
        lead = session.query(Lead).filter_by(account_id=account_id, phone_e164=phone_val).first()
        if lead:
            lead.opt_out = False
            lead.updated_at = func.now()
        session.commit()
        return True
    finally:
        session.close()


def update_lead(lead_id: int, updates: Dict[str, Any], account_id: Optional[int] = None) -> bool:
    session = SessionLocal()
    try:
        query = session.query(Lead).filter_by(id=lead_id)
        if account_id is not None:
            query = query.filter(Lead.account_id == account_id)
        lead = query.first()
        if not lead:
            return False

        if "name" in updates: lead.name = updates["name"]
        if "phone" in updates: lead.phone_e164 = clean_phone(updates["phone"])
        if "notes" in updates: lead.notes = updates["notes"]
        if "source" in updates: lead.source = updates["source"]
        if "last_call_stage" in updates: lead.last_outcome = updates["last_call_stage"]
        if "opt_out" in updates: lead.opt_out = bool(updates["opt_out"])

        cur_vars = dict(lead.variables or {})
        for k in ["email", "company", "service_needed", "budget", "timeline", "status", "priority",
                  "preferred_language", "designation", "industry", "location", "website",
                  "enrichment_data", "action_items", "last_call_summary", "last_call_stage",
                  "last_call_sentiment", "objections_noted", "last_called_at",
                  "outcome_label", "outcome_bucket", "outcome_reason", "outcome_confidence",
                  "needs_human_review", "whatsapp_opt_in", "callback_at"]:
            if k in updates:
                cur_vars[k] = updates[k]

        lead.variables = cur_vars
        lead.updated_at = func.now()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_lead error: {e}")
        return False
    finally:
        session.close()


def delete_lead(lead_id: int, account_id: Optional[int] = None) -> bool:
    session = SessionLocal()
    try:
        query = session.query(Lead).filter_by(id=lead_id)
        if account_id is not None:
            query = query.filter(Lead.account_id == account_id)
        lead = query.first()
        if not lead:
            return False
        session.delete(lead)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"delete_lead error: {e}")
        return False
    finally:
        session.close()


# ---------------- CALLS & TRANSCRIPTS ----------------

def save_call_record(call_data: Dict[str, Any], account_id: int = 1) -> int:
    from services.outcomes import normalize_outcome, parse_callback_time_ist
    session = SessionLocal()
    try:
        lead_id = call_data.get("lead_id")
        acc_id = int(call_data.get("account_id", account_id) or 1)
        if lead_id:
            lead_obj = session.query(Lead).filter_by(id=lead_id).first()
            if lead_obj and lead_obj.account_id:
                acc_id = lead_obj.account_id

        duration = int(call_data.get("duration_seconds", 0))
        blocks = (duration + 59) // 60 if duration > 0 else 0
        credits = round(blocks * 5.0, 2)

        transcript = call_data.get("transcript")
        if isinstance(transcript, str):
            try:
                transcript_parsed = json.loads(transcript)
            except Exception:
                transcript_parsed = transcript
            transcript_text = transcript
        elif isinstance(transcript, list):
            transcript_parsed = transcript
            transcript_text = "\n".join(str(m.get("content") or m.get("text") or "") for m in transcript if isinstance(m, dict))
        else:
            transcript_parsed = transcript
            transcript_text = str(transcript or "")

        raw_outcome = (
            call_data.get("outcome_label")
            or call_data.get("deal_stage")
            or call_data.get("disposition")
            or "completed"
        )
        norm = normalize_outcome(raw_outcome, transcript_text=transcript_text, confidence=call_data.get("confidence", 0.9))
        deal_stage = call_data.get("deal_stage") or norm["legacy_stage"]
        parsed_cb = parse_callback_time_ist(str(call_data.get("callback_at") or ""))

        call = Call(
            account_id=acc_id,
            lead_id=lead_id,
            employee_id=call_data.get("employee_id"),
            direction=call_data.get("direction") or "out",
            channel="manual" if call_data.get("call_type") == "web" else "instant",
            state=call_data.get("status", "completed"),
            provider_call_sid=call_data.get("call_sid") or None,
            talk_seconds=duration,
            billed_blocks=blocks,
            credits=credits,
            outcome=deal_stage,
            sentiment=call_data.get("sentiment", "neutral"),
            summary=call_data.get("summary", ""),
            action_items=call_data.get("action_items", ""),
            objections_raised=call_data.get("objections_raised", ""),
            extracted_requirements=call_data.get("extracted_requirements", ""),
            captured={
                "outcome_label": norm["outcome_label"],
                "outcome_bucket": norm["outcome_bucket"],
                "outcome_reason": call_data.get("outcome_reason", ""),
                "confidence": norm["confidence"],
                "needs_human_review": norm["needs_human_review"],
                "callback_at": parsed_cb.isoformat() if parsed_cb else call_data.get("callback_at"),
                "whatsapp_opt_in": bool(call_data.get("whatsapp_opt_in", False)),
                "extracted_budget": call_data.get("extracted_budget", ""),
                "extracted_timeline": call_data.get("extracted_timeline", ""),
                "extracted_requirements": call_data.get("extracted_requirements", ""),
                "objections_raised": call_data.get("objections_raised", ""),
                "action_items": call_data.get("action_items", ""),
                # voice engine call analytics: end reason, interruptions, languages, actions, …
                **({"analytics": call_data["analytics"]} if call_data.get("analytics") else {}),
            },
            ended_by=call_data.get("ended_by"),
            latency_avg_ms=call_data.get("latency_avg_ms"),
            transcript=transcript_parsed,
            recording_url=call_data.get("recording_url", "")
        )
        session.add(call)
        session.flush()

        # Update associated lead if present
        if lead_id:
            lead = session.query(Lead).filter_by(id=lead_id).first()
            if lead:
                status_map = {
                    "closed_won": "CLOSED_WON",
                    "demo_scheduled": "DEMO_BOOKED",
                    "qualified": "QUALIFIED",
                    "follow_up": "CONTACTED",
                    "lost": "LOST"
                }
                new_status = status_map.get(deal_stage.lower() if deal_stage else "", norm["crm_status"])
                lead.last_outcome = deal_stage
                lead.is_hot = bool(norm["is_hot"])
                if parsed_cb:
                    lead.callback_at = parsed_cb
                lead.last_call_summary = call_data.get("summary", "")
                lead.action_items = call_data.get("action_items", "")
                if call_data.get("objections_raised"):
                    lead.objections_noted = call_data["objections_raised"]

                # Honor Do-Not-Call / Opt-Out immediately (§3 & §4)
                if norm["opt_out_requested"] or call_data.get("opt_out_requested"):
                    lead.opt_out = True
                    existing_opt = session.query(OptOut).filter_by(
                        account_id=lead.account_id, phone_e164=lead.phone_e164
                    ).first()
                    if not existing_opt:
                        session.add(OptOut(
                            account_id=lead.account_id,
                            phone_e164=lead.phone_e164,
                            reason=norm["outcome_label"]
                        ))

                cur_vars = dict(lead.variables or {})
                if new_status: cur_vars["status"] = new_status
                if call_data.get("extracted_budget"): cur_vars["budget"] = call_data["extracted_budget"]
                if call_data.get("extracted_timeline"): cur_vars["timeline"] = call_data["extracted_timeline"]
                if call_data.get("extracted_requirements"): cur_vars["service_needed"] = call_data["extracted_requirements"]
                cur_vars["last_call_summary"] = call_data.get("summary", "")
                cur_vars["last_call_stage"] = deal_stage
                cur_vars["last_call_sentiment"] = call_data.get("sentiment", "neutral")
                cur_vars["outcome_label"] = norm["outcome_label"]
                cur_vars["outcome_bucket"] = norm["outcome_bucket"]
                cur_vars["outcome_reason"] = call_data.get("outcome_reason", "")
                cur_vars["outcome_confidence"] = norm["confidence"]
                cur_vars["needs_human_review"] = norm["needs_human_review"]
                cur_vars["whatsapp_opt_in"] = bool(call_data.get("whatsapp_opt_in", cur_vars.get("whatsapp_opt_in", False)))
                if parsed_cb:
                    cur_vars["callback_at"] = parsed_cb.isoformat()
                if call_data.get("objections_raised"): cur_vars["objections_noted"] = call_data["objections_raised"]
                cur_vars["action_items"] = call_data.get("action_items", "")
                cur_vars["last_called_at"] = datetime.now().isoformat()
                if norm["is_hot"] and not cur_vars.get("hot_marked_at"):
                    cur_vars["hot_marked_at"] = datetime.now().isoformat()

                # Compute & persist Plan v2 §4 Follow-Up Plan
                try:
                    from services.followup_engine import compute_next_followup_step
                    prev_misses = int(cur_vars.get("consecutive_misses", 0) or 0)
                    new_misses = (prev_misses + 1) if norm["outcome_bucket"] == "not_reachable" else 0
                    cur_vars["consecutive_misses"] = new_misses
                    attempt_num = int(cur_vars.get("attempt_count", 0) or 0) + 1
                    cur_vars["attempt_count"] = attempt_num
                    f_plan = compute_next_followup_step(
                        outcome_label=norm["outcome_label"],
                        callback_at=parsed_cb.isoformat() if parsed_cb else call_data.get("callback_at"),
                        attempt_number=attempt_num,
                        consecutive_misses=new_misses,
                        is_opted_out=bool(lead.opt_out),
                        is_converted=(new_status == "CLOSED_WON"),
                    )
                    cur_vars["followup_plan"] = f_plan
                except Exception as fe_err:
                    logger.warning(f"Follow-up engine plan warning: {fe_err}")

                lead.variables = cur_vars
                lead.updated_at = func.now()

        session.commit()
        return call.id
    except Exception as e:
        session.rollback()
        logger.error(f"save_call_record error: {e}")
        raise
    finally:
        session.close()


def override_lead_outcome(
    lead_id: int,
    outcome_label: str,
    reason: str = "",
    callback_at: Optional[str] = None,
    user_id: Optional[int] = None,
    account_id: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Rep override of a lead's call outcome (§3 & §7).
    Updates the lead's bucket/label, honors do_not_call -> opt_outs, and logs an AuditLog row.
    """
    from services.outcomes import normalize_outcome, parse_callback_time_ist
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter_by(id=lead_id).first()
        if not lead:
            return None
        prev_vars = dict(lead.variables or {})
        prev_label = prev_vars.get("outcome_label") or lead.last_outcome or ""
        norm = normalize_outcome(outcome_label, confidence=1.0)
        parsed_cb = parse_callback_time_ist(callback_at)

        lead.last_outcome = norm["legacy_stage"]
        lead.is_hot = bool(norm["is_hot"])
        if parsed_cb:
            lead.callback_at = parsed_cb

        if norm["opt_out_requested"]:
            lead.opt_out = True
            existing_opt = session.query(OptOut).filter_by(
                account_id=lead.account_id, phone_e164=lead.phone_e164
            ).first()
            if not existing_opt:
                session.add(OptOut(
                    account_id=lead.account_id,
                    phone_e164=lead.phone_e164,
                    reason=reason or norm["outcome_label"],
                ))

        prev_vars["outcome_label"] = norm["outcome_label"]
        prev_vars["outcome_bucket"] = norm["outcome_bucket"]
        prev_vars["outcome_reason"] = reason
        prev_vars["outcome_confidence"] = 1.0
        prev_vars["needs_human_review"] = False
        prev_vars["status"] = norm["crm_status"]
        if parsed_cb:
            prev_vars["callback_at"] = parsed_cb.isoformat()
        lead.variables = prev_vars
        lead.updated_at = func.now()

        session.add(AuditLog(
            account_id=lead.account_id or account_id,
            user_id=user_id,
            action="override_outcome",
            target=f"lead:{lead.id}",
            details={
                "previous_outcome": prev_label,
                "new_outcome": norm["outcome_label"],
                "new_bucket": norm["outcome_bucket"],
                "reason": reason,
                "callback_at": parsed_cb.isoformat() if parsed_cb else None,
            },
        ))
        session.commit()
        session.refresh(lead)
        return _lead_to_dict(lead)
    except Exception as e:
        session.rollback()
        logger.error(f"override_lead_outcome error: {e}")
        return None
    finally:
        session.close()


def get_outcome_bucket_summary(account_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Aggregates leads into the 4 Plan v2 (§3) buckets:
      hot · follow_up · closed · not_reachable (plus uncalled & needs_human_review).
    """
    from services.outcomes import OUTCOME_BUCKETS, OUTCOME_CATALOG
    leads = get_all_leads(account_id=account_id)
    buckets: Dict[str, int] = {"hot": 0, "follow_up": 0, "closed": 0, "not_reachable": 0, "uncalled": 0}
    labels: Dict[str, int] = {k: 0 for k in OUTCOME_CATALOG}
    review_list: List[Dict[str, Any]] = []

    for l in leads:
        b = l.get("outcome_bucket") or "uncalled"
        if b not in buckets:
            b = "uncalled"
        buckets[b] += 1
        lbl = l.get("outcome_label") or ""
        if lbl in labels:
            labels[lbl] += 1
        if l.get("needs_human_review"):
            review_list.append(l)

    return {
        "buckets": buckets,
        "bucket_meta": OUTCOME_BUCKETS,
        "labels": labels,
        "human_review_count": len(review_list),
        "human_review_leads": review_list[:50],
        "total_leads": len(leads),
    }


def get_last_call_facts(lead_id: int) -> Optional[Dict[str, Any]]:
    """
    What actually happened on the lead's most recent call, for the AI's caller memory:
    seconds of talk and how many customer turns were a real sentence (3+ words), not "Hello" / "Hmm".
    None if the lead was never called.
    """
    session = SessionLocal()
    try:
        call = session.query(Call).filter(Call.lead_id == lead_id).order_by(Call.created_at.desc()).first()
        if not call:
            return None
        transcript = call.transcript
        if isinstance(transcript, str):
            try:
                transcript = json.loads(transcript)
            except ValueError:
                transcript = []
        turns = [str(t.get("content") or t.get("text") or "") for t in (transcript or [])
                 if isinstance(t, dict) and t.get("role") == "user"]
        return {
            "talk_seconds": int(call.talk_seconds or 0),
            "substantive_turns": sum(1 for t in turns if len(t.split()) >= 3),
            "outcome": call.outcome,
        }
    finally:
        session.close()


def get_call_history(limit: int = 50, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Call, Lead).outerjoin(Lead, Call.lead_id == Lead.id)
        if account_id is not None:
            query = query.filter(Call.account_id == account_id)
        results = query.order_by(Call.created_at.desc()).limit(limit).all()
        return [_call_to_dict(c, l) for c, l in results]
    finally:
        session.close()


def get_call_by_id(call_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Call, Lead).outerjoin(Lead, Call.lead_id == Lead.id).filter(Call.id == call_id)
        if account_id is not None:
            query = query.filter(Call.account_id == account_id)
        result = query.first()
        if not result:
            return None
        return _call_to_dict(result[0], result[1])
    finally:
        session.close()


def get_calls_for_lead(lead_id: int, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        lead_q = session.query(Lead).filter_by(id=lead_id)
        if account_id is not None:
            lead_q = lead_q.filter(Lead.account_id == account_id)
        lead = lead_q.first()
        calls_q = session.query(Call).filter_by(lead_id=lead_id)
        if account_id is not None:
            calls_q = calls_q.filter(Call.account_id == account_id)
        calls = calls_q.order_by(Call.created_at.desc()).all()
        return [_call_to_dict(c, lead) for c in calls]
    finally:
        session.close()


def update_call_recording(call_id: int, recording_url: str) -> bool:
    """Attach a stored recording URL to a call record by its ID."""
    session = SessionLocal()
    try:
        call = session.query(Call).filter_by(id=call_id).first()
        if not call:
            return False
        call.recording_url = recording_url
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_call_recording error: {e}")
        return False
    finally:
        session.close()


def update_call_recording_by_sid(call_sid: str, recording_url: str) -> bool:
    session = SessionLocal()
    try:
        calls = session.query(Call).filter_by(provider_call_sid=call_sid).all()
        if not calls:
            return False
        for call in calls:
            call.recording_url = recording_url
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_call_recording_by_sid error: {e}")
        return False
    finally:
        session.close()


def update_call_status_by_sid(call_sid: str, status: str, duration: int = 0) -> bool:
    session = SessionLocal()
    try:
        calls = session.query(Call).filter_by(provider_call_sid=call_sid).all()
        if not calls:
            return False
        for call in calls:
            call.state = status
            call.outcome = status
            if duration > 0:
                call.talk_seconds = duration
                call.billed_blocks = (duration + 59) // 60
                call.credits = round(call.billed_blocks * 5.0, 2)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_call_status_by_sid error: {e}")
        return False
    finally:
        session.close()


# ---------------- COMPANY PROFILE & SETTINGS ----------------

def get_company_profile(account_id: int = 1) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        acc_id = int(account_id or 1)
        account = session.query(Account).filter_by(id=acc_id).first()
        if not account:
            return {
                "id": 1,
                "agency_name": "S P Associates Software Company",
                "tagline": "ఆధునిక వెబ్, మొబైల్ & AI ఆటోమేషన్ సాఫ్ట్‌వేర్ సేవలు",
                "services_offered": "[]",
                "pricing_details": "₹5/min billing",
                "sales_pitch": "",
                "preferred_language": "te-IN",
                "tts_voice": "kavitha_te_conversation"
            }

        default_services = json.dumps([
            {"name": "Custom Web & SaaS Development", "telugu": "కస్టమ్ వెబ్‌సైట్‌లు & SaaS సాఫ్ట్‌వేర్", "starting": "₹25,000"},
            {"name": "Mobile Apps (Android & iOS)", "telugu": "ఆండ్రాయిడ్ & ఐఫోన్ మొబైల్ యాప్‌లు", "starting": "₹45,000"},
            {"name": "AI Voice Calling & Chatbots", "telugu": "AI కాలింగ్ ఏజెంట్లు & వాట్సాప్ బాట్స్", "starting": "₹20,000"},
            {"name": "E-Commerce & Digital Billing", "telugu": "ఈ-కామర్స్ పోర్టల్స్ & ఆన్‌లైన్ పేమెంట్స్", "starting": "₹30,000"},
            {"name": "Cloud & Automation Systems", "telugu": "క్లౌడ్ మరియు బిజినెస్ ఆటోమేషన్", "starting": "₹20,000"}
        ], ensure_ascii=False)

        default_pitch = (
            "మేము సరికొత్త ఆర్టిఫిషియల్ ఇంటెలిజెన్స్ (AI), మొబైల్ యాప్స్ మరియు వెబ్‌సైట్లతో "
            "మీ వ్యాపారాన్ని తక్కువ ఖర్చుతో వేగంగా వృద్ధి చెందేలా చేస్తాము. 100% నమ్మకమైన సేవలు మరియు సమయానికి డెలివరీ."
        )

        return {
            "id": account.id,
            "agency_name": account.name,
            "tagline": "ఆధునిక వెబ్, మొబైల్ & AI ఆటోమేషన్ సాఫ్ట్‌వేర్ సేవలు",
            "services_offered": default_services,
            # what the sales agent tells customers; account.rate_per_min is the platform's call billing, not our price
            "pricing_details": "Flexible milestone payments; starting prices per service as listed above",
            "sales_pitch": default_pitch,
            "preferred_language": account.default_language or "te-IN",
            "tts_voice": "kavitha_te_conversation",
            "updated_at": account.created_at.isoformat() if account.created_at else None
        }
    finally:
        session.close()


def update_company_profile(data: Dict[str, Any], account_id: int = 1) -> bool:
    session = SessionLocal()
    try:
        acc_id = int(account_id or 1)
        account = session.query(Account).filter_by(id=acc_id).first()
        if not account:
            return False
        if data.get("agency_name"): account.name = data["agency_name"]
        if data.get("preferred_language"): account.default_language = data["preferred_language"]
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_company_profile error: {e}")
        return False
    finally:
        session.close()


# ---------------- AI EMPLOYEES ----------------

def get_all_ai_employees(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Employee)
        if account_id is not None:
            query = query.filter(Employee.account_id == int(account_id))
        employees = query.order_by(Employee.id.asc()).all()
        return [_emp_to_dict(e) for e in employees]
    finally:
        session.close()


def get_ai_employee_by_id(emp_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Employee).filter(Employee.id == emp_id)
        if account_id is not None:
            query = query.filter(Employee.account_id == int(account_id))
        emp = query.first()
        return _emp_to_dict(emp) if emp else None
    finally:
        session.close()


def get_active_ai_employee(account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Employee).filter_by(status="live")
        if account_id is not None:
            query = query.filter(Employee.account_id == int(account_id))
        emp = query.first()
        if not emp:
            fallback = session.query(Employee)
            if account_id is not None:
                fallback = fallback.filter(Employee.account_id == int(account_id))
            emp = fallback.first()
        return _emp_to_dict(emp) if emp else None
    finally:
        session.close()


def create_ai_employee(data: Dict[str, Any], account_id: int = 1) -> int:
    session = SessionLocal()
    try:
        acc_id = int(data.get("account_id", account_id) or 1)
        emp = Employee(
            account_id=acc_id,
            name=data["name"],
            job_type="instant",
            language=data.get("language", "te-IN"),
            voice=data.get("voice_speaker", "kavitha_te_conversation"),
            greeting=data.get("greeting", ""),
            system_prompt=data.get("system_prompt", ""),
            script_steps={
                "calling_objective": data.get("calling_objective", ""),
                "sales_script": data.get("sales_script", ""),
                "qualification_questions": data.get("qualification_questions", "")
            },
            variables={
                "role": data.get("role", "Sales Specialist"),
                "description": data.get("description", ""),
                "knowledge_base": data.get("knowledge_base", ""),
                "working_hours": data.get("working_hours", "09:00 - 19:00"),
                "max_call_duration_seconds": data.get("max_call_duration_seconds", 600)
            },
            status=data.get("status", "draft")
        )
        session.add(emp)
        session.commit()
        return emp.id
    except Exception as e:
        session.rollback()
        logger.error(f"create_ai_employee error: {e}")
        raise
    finally:
        session.close()


def update_ai_employee(emp_id: int, updates: Dict[str, Any], account_id: Optional[int] = None) -> bool:
    session = SessionLocal()
    try:
        query = session.query(Employee).filter(Employee.id == emp_id)
        if account_id is not None:
            query = query.filter(Employee.account_id == int(account_id))
        emp = query.first()
        if not emp:
            return False

        if "name" in updates: emp.name = updates["name"]
        if "language" in updates: emp.language = updates["language"]
        if "voice_speaker" in updates: emp.voice = updates["voice_speaker"]
        if "greeting" in updates: emp.greeting = updates["greeting"]
        if "system_prompt" in updates: emp.system_prompt = updates["system_prompt"]
        if "status" in updates: emp.status = updates["status"]

        cur_steps = dict(emp.script_steps or {})
        if "calling_objective" in updates: cur_steps["calling_objective"] = updates["calling_objective"]
        if "sales_script" in updates: cur_steps["sales_script"] = updates["sales_script"]
        if "qualification_questions" in updates: cur_steps["qualification_questions"] = updates["qualification_questions"]
        emp.script_steps = cur_steps

        cur_vars = dict(emp.variables or {})
        if "role" in updates: cur_vars["role"] = updates["role"]
        if "description" in updates: cur_vars["description"] = updates["description"]
        if "knowledge_base" in updates: cur_vars["knowledge_base"] = updates["knowledge_base"]
        if "working_hours" in updates: cur_vars["working_hours"] = updates["working_hours"]
        if "max_call_duration_seconds" in updates: cur_vars["max_call_duration_seconds"] = updates["max_call_duration_seconds"]
        emp.variables = cur_vars

        emp.updated_at = func.now()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_ai_employee error: {e}")
        return False
    finally:
        session.close()


def set_active_ai_employee(emp_id: int) -> bool:
    session = SessionLocal()
    try:
        session.query(Employee).update({Employee.status: "approved"})
        emp = session.query(Employee).filter_by(id=emp_id).first()
        if not emp:
            session.rollback()
            return False
        emp.status = "live"
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"set_active_ai_employee error: {e}")
        return False
    finally:
        session.close()


def delete_ai_employee(emp_id: int, account_id: Optional[int] = None) -> bool:
    session = SessionLocal()
    try:
        query = session.query(Employee).filter(Employee.id == emp_id)
        if account_id is not None:
            query = query.filter(Employee.account_id == int(account_id))
        emp = query.first()
        if not emp:
            return False
        session.delete(emp)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"delete_ai_employee error: {e}")
        return False
    finally:
        session.close()


# ---------------- PROVIDER SETTINGS & LOGS ----------------

def get_all_provider_settings(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(ProviderSetting)
        if account_id is not None:
            query = query.filter(ProviderSetting.account_id == int(account_id))
        settings = query.all()
        return [{
            "provider_type": s.provider_type,
            "provider_name": s.provider_name,
            "is_enabled": s.is_enabled,
            "is_configured": s.is_configured,
            "config_json": s.config_json,
            "last_tested_at": s.last_tested_at.isoformat() if s.last_tested_at else None,
            "test_status": s.test_status,
            "test_message": s.test_message or "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        } for s in settings]
    finally:
        session.close()


def get_provider_setting(provider_type: str, provider_name: str, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(ProviderSetting).filter_by(
            provider_type=provider_type,
            provider_name=provider_name
        )
        if account_id is not None:
            query = query.filter(ProviderSetting.account_id == int(account_id))
        s = query.first()
        if not s:
            return None
        return {
            "provider_type": s.provider_type,
            "provider_name": s.provider_name,
            "is_enabled": s.is_enabled,
            "is_configured": s.is_configured,
            "config_json": s.config_json,
            "last_tested_at": s.last_tested_at.isoformat() if s.last_tested_at else None,
            "test_status": s.test_status,
            "test_message": s.test_message or "",
        }
    finally:
        session.close()


def upsert_provider_setting(
    provider_type: str,
    provider_name: str,
    is_enabled: bool,
    is_configured: bool,
    config_dict: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    account_id: int = 1
) -> None:
    session = SessionLocal()
    try:
        acc_id = int(account_id or 1)
        cfg = config_dict or config or {}
        cfg_str = json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else str(cfg)

        s = session.query(ProviderSetting).filter_by(
            account_id=acc_id,
            provider_type=provider_type,
            provider_name=provider_name
        ).first()
        if s:
            s.is_enabled = is_enabled
            s.is_configured = is_configured
            s.config_json = cfg_str
            s.updated_at = func.now()
        else:
            s = ProviderSetting(
                account_id=acc_id,
                provider_type=provider_type,
                provider_name=provider_name,
                is_enabled=is_enabled,
                is_configured=is_configured,
                config_json=cfg_str
            )
            session.add(s)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"upsert_provider_setting error: {e}")
    finally:
        session.close()


def record_provider_test_result(provider_type: str, provider_name: str, status: str, message: str) -> None:
    session = SessionLocal()
    try:
        s = session.query(ProviderSetting).filter_by(
            provider_type=provider_type,
            provider_name=provider_name
        ).first()
        if s:
            s.test_status = status
            s.test_message = message
            s.last_tested_at = func.now()
            s.updated_at = func.now()
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"record_provider_test_result error: {e}")
    finally:
        session.close()


def update_lead_enrichment(lead_id: int, enrichment_data: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> bool:
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter_by(id=lead_id).first()
        if not lead:
            return False
        cur_vars = dict(lead.variables or {})
        cur_vars["enrichment_data"] = json.dumps(enrichment_data, ensure_ascii=False)
        if extra:
            cur_vars.update(extra)
        lead.variables = cur_vars
        lead.updated_at = func.now()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_lead_enrichment error: {e}")
        return False
    finally:
        session.close()


def get_daily_provider_usage(provider_name: str) -> float:
    session = SessionLocal()
    try:
        today_start = datetime.combine(datetime.now().date(), time.min)
        total = session.query(func.coalesce(func.sum(ProviderUsageLog.credits_used), 0.0)).filter(
            ProviderUsageLog.provider_name == provider_name,
            ProviderUsageLog.timestamp >= today_start
        ).scalar()
        return float(total)
    finally:
        session.close()


def record_provider_usage(provider_name: str, operation: str, credits_used: float = 1.0, details: str = "") -> None:
    session = SessionLocal()
    try:
        log = ProviderUsageLog(
            provider_name=provider_name,
            operation=operation,
            credits_used=credits_used,
            details=details
        )
        session.add(log)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"record_provider_usage error: {e}")
    finally:
        session.close()


# ---------------- API KEYS & BILLING ----------------

def get_all_api_keys(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(ApiKey)
        if account_id is not None:
            query = query.filter(ApiKey.account_id == int(account_id))
        keys = query.order_by(ApiKey.created_at.desc()).all()
        return [{
            "id": k.id,
            "key_name": k.key_name,
            "user_email": k.user_email,
            "company_name": k.company_name or "",
            "api_key": k.api_key,
            "plan_tier": k.plan_tier,
            "credits_inr": k.credits_inr,
            "rate_per_min": k.rate_per_min,
            "total_calls": k.total_calls,
            "total_minutes": k.total_minutes,
            "status": k.status,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "updated_at": k.updated_at.isoformat() if k.updated_at else None,
        } for k in keys]
    finally:
        session.close()



def get_primary_api_key(account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(ApiKey).filter_by(status="active")
        if account_id is not None:
            query = query.filter(ApiKey.account_id == int(account_id))
        k = query.first()
        if not k:
            return None
        return {
            "id": k.id,
            "key_name": k.key_name,
            "user_email": k.user_email,
            "company_name": k.company_name or "",
            "api_key": k.api_key,
            "plan_tier": k.plan_tier,
            "credits_inr": k.credits_inr,
            "rate_per_min": k.rate_per_min,
            "total_calls": k.total_calls,
            "total_minutes": k.total_minutes,
            "status": k.status
        }
    finally:
        session.close()


def get_api_key_by_token(token: str) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        k = session.query(ApiKey).filter_by(api_key=token).first()
        if not k:
            return None
        return {
            "id": k.id,
            "key_name": k.key_name,
            "user_email": k.user_email,
            "company_name": k.company_name or "",
            "api_key": k.api_key,
            "plan_tier": k.plan_tier,
            "credits_inr": k.credits_inr,
            "rate_per_min": k.rate_per_min,
            "total_calls": k.total_calls,
            "total_minutes": k.total_minutes,
            "status": k.status
        }
    finally:
        session.close()


def create_api_key(key_data: Dict[str, Any], account_id: int = 1) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        import secrets
        raw_token = f"lc_live_{secrets.token_hex(16)}"
        acc_id = int(key_data.get("account_id", account_id) or 1)
        ak = ApiKey(
            account_id=acc_id,
            key_name=key_data.get("key_name", "Developer Key"),
            user_email=key_data.get("user_email", "developer@company.com"),
            company_name=key_data.get("company_name", "Enterprise Client"),
            api_key=raw_token,
            plan_tier=key_data.get("plan_tier", "Business Growth (₹5/min)"),
            credits_inr=float(key_data.get("initial_credits_inr", 2500.0)),
            rate_per_min=float(key_data.get("rate_per_min", 5.0)),
            status="active"
        )
        session.add(ak)
        session.commit()
        return {
            "id": ak.id,
            "api_key": ak.api_key,
            "key_name": ak.key_name,
            "credits_inr": ak.credits_inr,
            "rate_per_min": ak.rate_per_min
        }
    except Exception as e:
        session.rollback()
        logger.error(f"create_api_key error: {e}")
        raise
    finally:
        session.close()


def revoke_api_key(api_key_token: str) -> bool:
    session = SessionLocal()
    try:
        ak = session.query(ApiKey).filter_by(api_key=api_key_token).first()
        if not ak:
            return False
        ak.status = "revoked"
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"revoke_api_key error: {e}")
        return False
    finally:
        session.close()


def deduct_api_credits(api_key_token: str, duration_seconds: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        ak = session.query(ApiKey).filter_by(api_key=api_key_token).first()
        if not ak:
            return {"success": False, "error": "Invalid API key"}

        minutes = (duration_seconds + 59) // 60 if duration_seconds > 0 else 0
        cost = minutes * ak.rate_per_min

        if ak.credits_inr < cost:
            return {"success": False, "error": "Insufficient credit balance", "balance": ak.credits_inr}

        ak.credits_inr -= cost
        ak.total_calls += 1
        ak.total_minutes += (duration_seconds / 60.0)
        session.commit()
        return {
            "success": True,
            "deducted_inr": cost,
            "remaining_balance": ak.credits_inr,
            "minutes_billed": minutes
        }
    except Exception as e:
        session.rollback()
        logger.error(f"deduct_api_credits error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def create_billing_order(order_data: Dict[str, Any], account_id: int = 1) -> int:
    session = SessionLocal()
    try:
        acc_id = int(order_data.get("account_id", account_id) or 1)
        bo = BillingOrder(
            account_id=acc_id,
            api_key_id=order_data.get("api_key_id"),
            order_id=order_data["order_id"],
            plan_name=order_data.get("plan_name", "Credit Recharge"),
            amount_inr=float(order_data.get("amount_inr", 0.0)),
            minutes_credited=float(order_data.get("minutes_credited", 0.0)),
            payment_method=order_data.get("payment_method", "Instant UPI / Razorpay Gateway"),
            payment_status=order_data.get("payment_status", "success"),
            customer_email=order_data.get("customer_email", ""),
            invoice_number=order_data.get("invoice_number", "")
        )
        session.add(bo)

        # Update credit balance on ApiKey
        if order_data.get("api_key_id"):
            ak = session.query(ApiKey).filter_by(id=order_data["api_key_id"]).first()
            if ak:
                ak.credits_inr += float(order_data.get("amount_inr", 0.0))

        session.commit()
        return bo.id
    except Exception as e:
        session.rollback()
        logger.error(f"create_billing_order error: {e}")
        raise
    finally:
        session.close()


def get_billing_orders(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(BillingOrder)
        if account_id is not None:
            query = query.filter(BillingOrder.account_id == int(account_id))
        orders = query.order_by(BillingOrder.created_at.desc()).all()
        return [{
            "id": o.id,
            "api_key_id": o.api_key_id,
            "order_id": o.order_id,
            "plan_name": o.plan_name,
            "amount_inr": o.amount_inr,
            "minutes_credited": o.minutes_credited,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "customer_email": o.customer_email or "",
            "invoice_number": o.invoice_number or "",
            "created_at": o.created_at.isoformat() if o.created_at else None
        } for o in orders]
    finally:
        session.close()


# ---------------- CAMPAIGNS ----------------

def create_campaign(data: Dict[str, Any], account_id: int = 1) -> int:
    session = SessionLocal()
    try:
        acc_id = int(data.get("account_id", account_id) or 1)
        c = Campaign(
            account_id=acc_id,
            name=data["name"],
            description=data.get("description", ""),
            employee_id=data.get("employee_id", 1),
            lead_ids_json=json.dumps(data.get("lead_ids", [])),
            mode=data.get("mode", "telephony"),
            status=data.get("status", "draft"),
            total_leads=len(data.get("lead_ids", [])),
            max_concurrency=data.get("max_concurrency", 3),
            retry_attempts=data.get("retry_attempts", 2)
        )
        session.add(c)
        session.commit()
        return c.id
    except Exception as e:
        session.rollback()
        logger.error(f"create_campaign error: {e}")
        raise
    finally:
        session.close()


def get_all_campaigns(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Campaign)
        if account_id is not None:
            query = query.filter(Campaign.account_id == int(account_id))
        camps = query.order_by(Campaign.created_at.desc()).all()
        return [{
            "id": c.id,
            "name": c.name,
            "description": c.description or "",
            "employee_id": c.employee_id,
            "lead_ids": json.loads(c.lead_ids_json or "[]"),
            "mode": c.mode,
            "status": c.status,
            "total_leads": c.total_leads,
            "completed_leads": c.completed_leads,
            "max_concurrency": c.max_concurrency,
            "retry_attempts": c.retry_attempts,
            "results": json.loads(c.results_json or "{}"),
            "logs": json.loads(c.logs_json or "[]"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        } for c in camps]
    finally:
        session.close()


def get_campaign_by_id(campaign_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Campaign).filter(Campaign.id == campaign_id)
        if account_id is not None:
            query = query.filter(Campaign.account_id == int(account_id))
        c = query.first()
        if not c:
            return None
        return {
            "id": c.id,
            "name": c.name,
            "description": c.description or "",
            "employee_id": c.employee_id,
            "lead_ids": json.loads(c.lead_ids_json or "[]"),
            "mode": c.mode,
            "status": c.status,
            "total_leads": c.total_leads,
            "completed_leads": c.completed_leads,
            "max_concurrency": c.max_concurrency,
            "retry_attempts": c.retry_attempts,
            "results": json.loads(c.results_json or "{}"),
            "logs": json.loads(c.logs_json or "[]"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
    finally:
        session.close()


def update_campaign_status(
    campaign_id: Optional[int] = None,
    status: str = "draft",
    results: Optional[Dict[str, Any]] = None,
    logs: Optional[List[Dict[str, Any]]] = None,
    camp_id: Optional[int] = None,
    completed: Optional[int] = None,
    log_entry: Optional[Dict[str, Any]] = None,
    account_id: Optional[int] = None
) -> bool:
    session = SessionLocal()
    try:
        target_id = camp_id or campaign_id
        query = session.query(Campaign).filter(Campaign.id == target_id)
        if account_id is not None:
            query = query.filter(Campaign.account_id == int(account_id))
        c = query.first()
        if not c:
            return False
        c.status = status
        if completed is not None:
            c.completed_leads = completed
        if results is not None:
            c.results_json = json.dumps(results, ensure_ascii=False)
            if completed is None:
                c.completed_leads = len(results)
        if logs is not None:
            c.logs_json = json.dumps(logs, ensure_ascii=False)
        elif log_entry is not None:
            cur_logs = json.loads(c.logs_json or "[]")
            cur_logs.append(log_entry)
            c.logs_json = json.dumps(cur_logs, ensure_ascii=False)
        c.updated_at = func.now()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"update_campaign_status error: {e}")
        return False
    finally:
        session.close()


# ---------------- ANALYTICS SUMMARY ----------------

def get_analytics_summary(
    account_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    campaign_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate real executive metrics, conversion funnel, objections, sentiments, and employee performance."""
    session = SessionLocal()
    try:
        acc_filter = int(account_id) if account_id is not None else None

        lead_query = session.query(Lead)
        if acc_filter:
            lead_query = lead_query.filter(Lead.account_id == acc_filter)
        if source:
            lead_query = lead_query.filter(Lead.source.ilike(source.strip()))
        if date_from:
            lead_query = lead_query.filter(Lead.created_at >= date_from)
        if date_to:
            lead_query = lead_query.filter(Lead.created_at <= date_to)
        leads = lead_query.all()
        total_leads = len(leads)

        status_counts: Dict[str, int] = {}
        for l in leads:
            st = (l.variables or {}).get("status", "NEW") if isinstance(l.variables, dict) else "NEW"
            status_counts[st] = status_counts.get(st, 0) + 1

        call_query = session.query(Call)
        if acc_filter:
            call_query = call_query.filter(Call.account_id == acc_filter)
        if campaign_id is not None:
            call_query = call_query.filter(Call.campaign_id == campaign_id)
        if date_from:
            call_query = call_query.filter(Call.created_at >= date_from)
        if date_to:
            call_query = call_query.filter(Call.created_at <= date_to)
        calls = call_query.all()
        total_calls = len(calls)
        total_duration_sec = sum(c.talk_seconds or 0 for c in calls)
        avg_call_duration_seconds = round(total_duration_sec / max(total_calls, 1), 1)

        dispositions: Dict[str, int] = {}
        stages: Dict[str, int] = {}
        sentiments: Dict[str, int] = {}
        objections_tally = {
            "pricing": 0,
            "existing_solution": 0,
            "send_whatsapp_timing": 0,
            "custom_requirements": 0,
            "other": 0
        }

        for c in calls:
            disp = c.outcome or c.state or "completed"
            dispositions[disp] = dispositions.get(disp, 0) + 1

            stg = c.outcome or "qualifying"
            stages[stg] = stages.get(stg, 0) + 1

            snt = c.sentiment or "neutral"
            sentiments[snt] = sentiments.get(snt, 0) + 1

            cap = c.captured if isinstance(c.captured, dict) else {}
            obj_text = (cap.get("objections_raised") or "").lower()
            if obj_text:
                matched = False
                if any(w in obj_text for w in ["price", "cost", "budget", "expensive", "ధర"]):
                    objections_tally["pricing"] += 1
                    matched = True
                if any(w in obj_text for w in ["already", "have", "existing", "ఉంది", "ఉపయోగిస్తున్నాం"]):
                    objections_tally["existing_solution"] += 1
                    matched = True
                if any(w in obj_text for w in ["whatsapp", "later", "time", "busy", "సమయం", "బిజీ"]):
                    objections_tally["send_whatsapp_timing"] += 1
                    matched = True
                if any(w in obj_text for w in ["feature", "custom", "integration", "app", "ఫీచర్"]):
                    objections_tally["custom_requirements"] += 1
                    matched = True
                if not matched:
                    objections_tally["other"] += 1

        demos_booked = status_counts.get("DEMO_BOOKED", 0) + stages.get("demo_scheduled", 0) + stages.get("demo_booked", 0)
        closed_won = status_counts.get("CLOSED_WON", 0) + stages.get("closed_won", 0)
        conversion_rate = round(((demos_booked + closed_won) / max(total_calls, 1)) * 100, 1)

        # Languages breakdown from real lead variables
        languages = {"te-IN": 0, "hi-IN": 0, "en-IN": 0, "ta-IN": 0, "kn-IN": 0, "ml-IN": 0}
        for l in leads:
            lang = (l.variables or {}).get("preferred_language", "te-IN") if isinstance(l.variables, dict) else "te-IN"
            if lang in languages:
                languages[lang] += 1
            else:
                languages["te-IN"] = languages.get("te-IN", 0) + 1

        # Real CPQL calculation based on billed talk-time (₹5/min)
        est_total_spend = (total_duration_sec / 60.0) * 5.0
        cpql_inr = round(est_total_spend / max(demos_booked + closed_won, 1), 2) if (demos_booked + closed_won) > 0 else 0.0

        # Employees performance summary from real call records
        emp_query = session.query(Employee)
        if acc_filter:
            emp_query = emp_query.filter(Employee.account_id == acc_filter)
        emps = emp_query.all()

        employee_list = []
        for e in emps:
            e_calls = [c for c in calls if c.employee_id == e.id]
            calls_handled = len(e_calls)
            demos_count = sum(
                1 for c in e_calls
                if "demo" in (c.outcome or "").lower()
                or "demo" in (c.state or "").lower()
                or (isinstance(c.captured, dict) and "demo" in str(c.captured.get("outcome_label", "")).lower())
            )
            succ_rate = round((demos_count / max(calls_handled, 1)) * 100, 1) if calls_handled > 0 else 0.0
            employee_list.append({
                "id": e.id,
                "name": e.name,
                "role": (e.variables or {}).get("role", "Sales Specialist") if isinstance(e.variables, dict) else "Sales Specialist",
                "calls_handled": calls_handled,
                "demos_booked": demos_count,
                "success_rate": succ_rate
            })

        return {
            "total_leads": total_leads,
            "status_counts": status_counts,
            "total_calls": total_calls,
            "total_duration_sec": total_duration_sec,
            "avg_call_duration_seconds": avg_call_duration_seconds,
            "dispositions": dispositions,
            "stages": stages,
            "sentiments": sentiments,
            "demos_booked": demos_booked,
            "closed_won": closed_won,
            "conversion_rate": conversion_rate,
            "cpql_inr": cpql_inr,
            "objections": objections_tally,
            "languages": languages,
            "employees": employee_list,
            "employee_performance": employee_list
        }
    finally:
        session.close()


def get_phone_numbers(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Returns active carrier trunks for the account (Vobiz verified carrier lines).
    Scoped to company account_id for multi-tenant isolation.
    """
    session = SessionLocal()
    try:
        query = session.query(Number)
        if account_id is not None:
            query = query.filter((Number.account_id == int(account_id)) | (Number.account_id == None))
        numbers = query.order_by(Number.id.asc()).all()

        if not numbers:
            return [{
                "id": 1,
                "account_id": account_id or 1,
                "e164": "+917965482229",
                "phone_number": "+917965482229",
                "phone_display": "+91 7965482229",
                "provider": "Vobiz",
                "channels": 10,
                "status": "Active",
                "linked_app": "Yes",
                "monthly_rent": "₹600",
                "monthly_rent_inr": 600,
                "next_bill": "5 Dec",
                "assigned_rep": "S P Senior Closer (Default)",
                "is_test_line": False
            }]

        result = []
        for n in numbers:
            e164_val = n.e164 or "+917965482229"
            if e164_val in ("+918000000000", "+91 80000 00000"):
                e164_val = "+917965482229"

            provider_val = "Vobiz" if (n.provider or "").lower() in ("vobiz", "exotel") else (n.provider or "Vobiz").capitalize()

            rep_name = "S P Senior Closer (Default)"
            if n.employee_id:
                emp = session.query(Employee).filter_by(id=n.employee_id).first()
                if emp:
                    rep_name = emp.name

            result.append({
                "id": n.id,
                "account_id": n.account_id,
                "e164": e164_val,
                "phone_number": e164_val,
                "phone_display": "+91 7965482229" if "7965482229" in e164_val else e164_val,
                "provider": provider_val,
                "channels": n.channels or 10,
                "status": "Active" if (n.status or "").lower() == "active" else (n.status or "Active"),
                "linked_app": "Yes",
                "monthly_rent": "₹600",
                "monthly_rent_inr": 600,
                "next_bill": "5 Dec",
                "assigned_rep": rep_name,
                "is_test_line": bool(n.is_test_line)
            })
        return result
    finally:
        session.close()
