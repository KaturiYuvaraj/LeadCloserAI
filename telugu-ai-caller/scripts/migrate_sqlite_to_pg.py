"""
Migration script: SQLite -> PostgreSQL.
Migrates company_profile (to Account), users, ai_employees (to Employee),
leads, calls, provider_settings, api_keys, and billing_orders.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Add telugu-ai-caller to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from core.db import DATABASE_URL, Base
from models import (
    Account,
    User,
    Number,
    Employee,
    Lead,
    Call,
    ProviderSetting,
    ProviderUsageLog,
    ApiKey,
    BillingOrder
)

SQLITE_PATH = PROJECT_DIR / "leads_crm.db"


def clean_phone(raw: str) -> str:
    """Normalize phone string into E.164-compatible format."""
    if not raw:
        return "+910000000000"
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    elif digits:
        return f"+{digits}"
    return "+910000000000"


def run_migration():
    if not SQLITE_PATH.exists():
        logger.warning(f"SQLite DB not found at {SQLITE_PATH}, nothing to migrate.")
        return

    logger.info(f"Connecting to SQLite database at {SQLITE_PATH}...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    logger.info(f"Connecting to PostgreSQL at {DATABASE_URL}...")
    pg_engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=pg_engine)
    session = Session()

    try:
        # Clear existing data in reverse dependency order for clean idempotent migration
        session.execute(text("TRUNCATE TABLE calls, credit_ledger, audit_log, opt_outs, leads, employees, numbers, users, api_billing_orders, api_keys, accounts, provider_settings, provider_usage_logs RESTART IDENTITY CASCADE;"))
        session.commit()

        # 1. Migrate / Create default Account
        account = Account(
            id=1,
            name="S P Associates Software Company",
            default_language="te-IN",
            calling_approved=True,
            rate_per_min=5.00
        )
        session.add(account)
        session.commit()
        logger.info(f"Created default Account #{account.id}: {account.name}")

        # 2. Migrate / Create default User
        user = User(
            id=1,
            account_id=account.id,
            email="admin@leadcloser.ai",
            password_hash="pbkdf2:sha256:default_hash_for_admin",
            role="owner"
        )
        session.add(user)
        session.commit()
        logger.info(f"Created default User: {user.email}")

        # 3. Migrate / Create default Number
        number = Number(
            id=1,
            account_id=account.id,
            e164="+918000000000",
            provider="exotel",
            channels=10,
            status="active"
        )
        session.add(number)
        session.commit()
        logger.info(f"Created default Number: {number.e164}")

        # 4. Migrate AI Employees -> Employees
        try:
            sqlite_cur.execute("SELECT * FROM ai_employees")
            emp_rows = sqlite_cur.fetchall()
            logger.info(f"Migrating {len(emp_rows)} AI employees...")
            for er in emp_rows:
                status = "live" if er["is_active"] else ("testing" if er["status"] == "approved" else "draft")
                emp = Employee(
                    id=er["id"],
                    account_id=account.id,
                    name=er["name"],
                    job_type="bulk" if "Campaign" in er["name"] else "instant",
                    language=er["language"] or "te-IN",
                    voice=er["voice_speaker"] or "kavitha_te_conversation",
                    tier="standard",
                    greeting=er["greeting"] or "",
                    system_prompt=er["system_prompt"] or "",
                    script_steps={
                        "sales_script": er["sales_script"] or "",
                        "qualification_questions": er["qualification_questions"] or "",
                        "calling_objective": er["calling_objective"] or ""
                    },
                    variables={
                        "role": er["role"] or "",
                        "description": er["description"] or "",
                        "knowledge_base": er["knowledge_base"] or "",
                        "working_hours": er["working_hours"] or "09:00 - 19:00"
                    },
                    status=status,
                    number_id=number.id
                )
                session.add(emp)
            session.commit()
            logger.info("Migrated employees successfully.")
        except Exception as e:
            session.rollback()
            logger.warning(f"AI Employees migration note: {e}")

        # 5. Migrate Leads
        valid_lead_ids = set()
        try:
            sqlite_cur.execute("SELECT * FROM leads ORDER BY id ASC")
            lead_rows = sqlite_cur.fetchall()
            logger.info(f"Migrating {len(lead_rows)} leads...")
            seen_phones = {}

            for lr in lead_rows:
                base_phone = clean_phone(lr["phone"])
                # Maintain unique constraint per account
                if base_phone in seen_phones:
                    seen_phones[base_phone] += 1
                    phone = f"{base_phone}-{seen_phones[base_phone]}"
                else:
                    seen_phones[base_phone] = 1
                    phone = base_phone

                status = lr["status"] if "status" in lr.keys() else "NEW"
                priority = lr["priority"] if "priority" in lr.keys() else "MEDIUM"
                is_hot = True if priority == "HIGH" or (lr["last_call_sentiment"] if "last_call_sentiment" in lr.keys() else None) == "positive" else False

                variables = {
                    "email": lr["email"] if "email" in lr.keys() else None,
                    "company": lr["company"] if "company" in lr.keys() else None,
                    "service_needed": lr["service_needed"] if "service_needed" in lr.keys() else None,
                    "budget": lr["budget"] if "budget" in lr.keys() else None,
                    "timeline": lr["timeline"] if "timeline" in lr.keys() else None,
                    "status": status,
                    "priority": priority,
                    "designation": lr["designation"] if "designation" in lr.keys() else None,
                    "industry": lr["industry"] if "industry" in lr.keys() else None,
                    "location": lr["location"] if "location" in lr.keys() else None,
                    "website": lr["website"] if "website" in lr.keys() else None,
                    "enrichment_data": lr["enrichment_data"] if "enrichment_data" in lr.keys() else None
                }

                lead = Lead(
                    id=lr["id"],
                    account_id=account.id,
                    name=lr["name"] or "Lead",
                    phone_e164=phone,
                    source=lr["source"] if "source" in lr.keys() and lr["source"] else "manual",
                    variables=variables,
                    consent_source="crm_import",
                    opt_out=False,
                    last_outcome=lr["last_call_stage"] if "last_call_stage" in lr.keys() else None,
                    is_hot=is_hot,
                    notes=lr["notes"] if "notes" in lr.keys() else None
                )
                session.add(lead)
                valid_lead_ids.add(lr["id"])

            session.commit()
            logger.info(f"Migrated {len(valid_lead_ids)} leads successfully.")
        except Exception as e:
            session.rollback()
            logger.warning(f"Leads migration note: {e}")

        # 6. Migrate Calls
        try:
            sqlite_cur.execute("SELECT * FROM calls ORDER BY id ASC")
            call_rows = sqlite_cur.fetchall()
            logger.info(f"Migrating {len(call_rows)} call records...")
            migrated_calls_count = 0

            for cr in call_rows:
                duration = cr["duration_seconds"] or 0
                blocks = (duration + 59) // 60 if duration > 0 else 0
                credits = round(blocks * 5.0, 2)

                transcript_val = None
                raw_t = cr["transcript"]
                if raw_t:
                    try:
                        transcript_val = json.loads(raw_t)
                    except Exception:
                        transcript_val = raw_t

                lead_id = cr["lead_id"]
                if lead_id not in valid_lead_ids:
                    lead_id = None

                call = Call(
                    id=cr["id"],
                    account_id=account.id,
                    lead_id=lead_id,
                    direction="out",
                    channel="manual" if cr["call_type"] == "web" else "instant",
                    state=cr["status"] or "completed",
                    provider_call_sid=cr["call_sid"] if "call_sid" in cr.keys() else None,
                    talk_seconds=duration,
                    billed_blocks=blocks,
                    credits=credits,
                    outcome=cr["disposition"] if "disposition" in cr.keys() and cr["disposition"] else cr["deal_stage"],
                    sentiment=cr["sentiment"] or "neutral",
                    summary=cr["summary"],
                    captured={
                        "extracted_budget": cr["extracted_budget"],
                        "extracted_timeline": cr["extracted_timeline"],
                        "extracted_requirements": cr["extracted_requirements"],
                        "objections_raised": cr["objections_raised"],
                        "action_items": cr["action_items"]
                    },
                    transcript=transcript_val,
                    recording_url=cr["recording_url"] if "recording_url" in cr.keys() else None
                )
                session.add(call)
                migrated_calls_count += 1

            session.commit()
            logger.info(f"Migrated {migrated_calls_count} calls successfully.")
        except Exception as e:
            session.rollback()
            logger.warning(f"Calls migration note: {e}")

        # 7. Migrate Provider Settings
        try:
            sqlite_cur.execute("SELECT * FROM provider_settings")
            ps_rows = sqlite_cur.fetchall()
            logger.info(f"Migrating {len(ps_rows)} provider settings...")
            for psr in ps_rows:
                ps = ProviderSetting(
                    provider_type=psr["provider_type"],
                    provider_name=psr["provider_name"],
                    is_enabled=bool(psr["is_enabled"]),
                    is_configured=bool(psr["is_configured"]),
                    config_json=psr["config_json"] or "{}",
                    test_status=psr["test_status"] or "untested",
                    test_message=psr["test_message"] or ""
                )
                session.add(ps)
            session.commit()
            logger.info("Migrated provider settings successfully.")
        except Exception as e:
            session.rollback()
            logger.warning(f"Provider settings migration note: {e}")

        # 8. Migrate API Keys
        try:
            sqlite_cur.execute("SELECT * FROM api_keys")
            ak_rows = sqlite_cur.fetchall()
            logger.info(f"Migrating {len(ak_rows)} api keys...")
            for akr in ak_rows:
                ak = ApiKey(
                    id=akr["id"],
                    key_name=akr["key_name"],
                    user_email=akr["user_email"],
                    company_name=akr["company_name"],
                    api_key=akr["api_key"],
                    plan_tier=akr["plan_tier"] or "Business Growth",
                    credits_inr=akr["credits_inr"] or 2500.0,
                    rate_per_min=akr["rate_per_min"] or 5.0,
                    total_calls=akr["total_calls"] or 0,
                    total_minutes=akr["total_minutes"] or 0.0,
                    status=akr["status"] or "active"
                )
                session.add(ak)
            session.commit()
            logger.info("Migrated API keys successfully.")
        except Exception as e:
            session.rollback()
            logger.warning(f"API Keys migration note: {e}")

        # Update sequences so new auto-increment IDs start past existing records
        for table in ["accounts", "users", "numbers", "employees", "leads", "calls", "api_keys"]:
            try:
                session.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id),0) + 1, false) FROM {table};"))
                session.commit()
            except Exception:
                session.rollback()

        logger.info("SQLite to PostgreSQL migration completed successfully!")

    except Exception as e:
        session.rollback()
        logger.error(f"Migration error: {e}")
        raise
    finally:
        session.close()
        sqlite_conn.close()


if __name__ == "__main__":
    run_migration()
