"""
SQLite Database module for Telugu AI Caller & Lead Closing CRM.
Manages leads, call histories, post-call deal analytics, and company profile.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from config import DATABASE_PATH


DB_FILE = Path(DATABASE_PATH)


def get_connection():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Leads table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        company TEXT,
        service_needed TEXT,
        budget TEXT,
        timeline TEXT,
        status TEXT DEFAULT 'NEW',
        priority TEXT DEFAULT 'MEDIUM',
        notes TEXT,
        last_call_summary TEXT,
        last_call_stage TEXT,
        last_call_sentiment TEXT,
        objections_noted TEXT,
        action_items TEXT,
        last_called_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Ensure columns exist in case of pre-existing DB
    cursor.execute("PRAGMA table_info(leads)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    new_cols = [
        ("last_call_summary", "TEXT"),
        ("last_call_stage", "TEXT"),
        ("last_call_sentiment", "TEXT"),
        ("objections_noted", "TEXT"),
        ("action_items", "TEXT"),
        ("last_called_at", "TIMESTAMP"),
        ("preferred_language", "TEXT DEFAULT 'te-IN'")
    ]
    for c_name, c_type in new_cols:
        if c_name not in existing_cols:
            cursor.execute(f"ALTER TABLE leads ADD COLUMN {c_name} {c_type}")

    # Calls history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        call_type TEXT DEFAULT 'web',
        phone_number TEXT,
        duration_seconds INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        summary TEXT,
        sentiment TEXT DEFAULT 'neutral',
        deal_stage TEXT DEFAULT 'qualifying',
        extracted_budget TEXT,
        extracted_timeline TEXT,
        extracted_requirements TEXT,
        objections_raised TEXT,
        action_items TEXT,
        transcript TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE SET NULL
    );
    """)

    # Company Profile & Knowledge Base table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY,
        agency_name TEXT DEFAULT 'S P Associates Software Company',
        tagline TEXT DEFAULT 'ఆధునిక వెబ్, మొబైల్ & AI ఆటోమేషన్ సాఫ్ట్‌వేర్ సేవలు',
        services_offered TEXT,
        pricing_details TEXT,
        target_audience TEXT,
        preferred_language TEXT DEFAULT 'te-IN',
        tts_voice TEXT DEFAULT 'kavitha_te_conversation',
        sales_pitch TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed or update default company profile
    cursor.execute("SELECT COUNT(*) as count FROM company_profile")
    if cursor.fetchone()["count"] == 0:
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

        cursor.execute("""
        INSERT INTO company_profile (id, agency_name, tagline, services_offered, pricing_details, sales_pitch)
        VALUES (1, ?, ?, ?, ?, ?)
        """, (
            'S P Associates Software Company',
            'ఆధునిక వెబ్, మొబైల్ & AI ఆటోమేషన్ సాఫ్ట్‌వేర్ సేవలు',
            default_services,
            'ఫ్లెక్సిబుల్ బడ్జెట్ మరియు మైల్‌స్టోన్ బేస్డ్ పేమెంట్స్ అందుబాటులో ఉన్నాయి.',
            default_pitch
        ))
    else:
        # Update any previous company name to S P Associates Software Company
        cursor.execute("""
        UPDATE company_profile
        SET agency_name = 'S P Associates Software Company'
        WHERE id = 1
        """)

    # Seed demo leads if leads table is empty
    cursor.execute("SELECT COUNT(*) as count FROM leads")
    if cursor.fetchone()["count"] == 0:
        seed_leads = [
            (
                "రమేష్ కుమార్ (Ramesh Kumar)",
                "+91 9876543210",
                "ramesh@hyderabadretails.com",
                "Hyderabad Retail Stores",
                "E-Commerce & Mobile App",
                "₹50,000 - ₹1,00,000",
                "Next 2 weeks",
                "NEW",
                "HIGH",
                "రిటైల్ షాపుల కోసం కస్టమర్ ఆర్డరింగ్ యాప్ మరియు వెబ్‌సైట్ కావాలి."
            ),
            (
                "సురేష్ వర్మ (Suresh Varma)",
                "+91 9848022338",
                "suresh@varma-logistics.in",
                "Varma Logistics & Transport",
                "AI Voice Calling & Automation",
                "₹75,000+",
                "Within 1 month",
                "QUALIFIED",
                "HIGH",
                "కస్టమర్ల బుకింగ్స్ మరియు స్టేటస్ అప్‌డేట్స్ కోసం ఆటోమేటెడ్ AI కాలింగ్ అవసరం."
            ),
            (
                "అనితారెడ్డి (Anita Reddy)",
                "+91 9701234567",
                "anita@reddyclinics.com",
                "Reddy Dental & Diagnostic Clinic",
                "Custom Website & Appointment Booking",
                "₹30,000 - ₹50,000",
                "Immediate",
                "CONTACTED",
                "MEDIUM",
                "రోగుల అపాయింట్‌మెంట్ బుకింగ్ కోసం ఆన్‌లైన్ పోర్టల్ మరియు వాట్సాప్ రిమైండర్లు."
            )
        ]
        cursor.executemany("""
        INSERT INTO leads (name, phone, email, company, service_needed, budget, timeline, status, priority, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_leads)

    # API Keys & Developer Licensing Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        company_name TEXT,
        api_key TEXT UNIQUE NOT NULL,
        plan_tier TEXT DEFAULT 'Business Growth',
        credits_inr REAL DEFAULT 2500.0,
        rate_per_min REAL DEFAULT 5.0,
        total_calls INTEGER DEFAULT 0,
        total_minutes REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # API Billing & Credit Purchases Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_billing_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        api_key_id INTEGER,
        order_id TEXT UNIQUE NOT NULL,
        plan_name TEXT NOT NULL,
        amount_inr REAL NOT NULL,
        minutes_credited REAL NOT NULL,
        payment_method TEXT DEFAULT 'UPI / Razorpay',
        payment_status TEXT DEFAULT 'success',
        customer_email TEXT,
        invoice_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (api_key_id) REFERENCES api_keys (id) ON DELETE SET NULL
    );
    """)

    # Seed default primary API key if api_keys table is empty
    cursor.execute("SELECT COUNT(*) as count FROM api_keys")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("""
        INSERT INTO api_keys (id, key_name, user_email, company_name, api_key, plan_tier, credits_inr, rate_per_min, total_calls, total_minutes, status)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'Production Master API Key',
            'enterprise@spassociates.com',
            'S P Associates Software Company',
            'lc_live_sp_assoc_7894a1b2',
            'Business Growth (₹5/min)',
            2500.0,
            5.0,
            14,
            28.5,
            'active'
        ))

        cursor.execute("""
        INSERT INTO api_billing_orders (api_key_id, order_id, plan_name, amount_inr, minutes_credited, payment_method, payment_status, customer_email, invoice_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            'ORD_2026_9841',
            'Business Growth Tier (500 Mins Talk-Time)',
            2500.0,
            500.0,
            'Instant UPI / Razorpay Gateway',
            'success',
            'enterprise@spassociates.com',
            'INV-SPA-2026-0049'
        ))

    conn.commit()
    conn.close()


# ---------------- CRUD FOR LEADS ----------------

def get_all_leads() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_lead(lead_data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO leads (name, phone, email, company, service_needed, budget, timeline, status, priority, notes, preferred_language)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead_data.get("name", ""),
        lead_data.get("phone", ""),
        lead_data.get("email", ""),
        lead_data.get("company", ""),
        lead_data.get("service_needed", "Custom Software"),
        lead_data.get("budget", "Flexible"),
        lead_data.get("timeline", "Immediate"),
        lead_data.get("status", "NEW"),
        lead_data.get("priority", "MEDIUM"),
        lead_data.get("notes", ""),
        lead_data.get("preferred_language", "te-IN")
    ))
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def batch_create_leads(leads: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Insert multiple leads from Excel/CSV.
    Skips exact duplicate phone numbers or updates them.
    Returns: (inserted_count, updated_count)
    """
    conn = get_connection()
    cursor = conn.cursor()
    inserted = 0
    updated = 0

    for lead in leads:
        phone = lead.get("phone", "").strip()
        if not phone:
            continue

        cursor.execute("SELECT id FROM leads WHERE phone = ?", (phone,))
        existing = cursor.fetchone()

        if existing:
            # Update existing lead with latest details
            cursor.execute("""
            UPDATE leads
            SET name = COALESCE(NULLIF(?, ''), name),
                company = COALESCE(NULLIF(?, ''), company),
                service_needed = COALESCE(NULLIF(?, ''), service_needed),
                budget = COALESCE(NULLIF(?, ''), budget),
                timeline = COALESCE(NULLIF(?, ''), timeline),
                notes = COALESCE(NULLIF(?, ''), notes),
                preferred_language = COALESCE(NULLIF(?, ''), preferred_language),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                lead.get("name"),
                lead.get("company"),
                lead.get("service_needed"),
                lead.get("budget"),
                lead.get("timeline"),
                lead.get("notes"),
                lead.get("preferred_language"),
                existing["id"]
            ))
            updated += 1
        else:
            cursor.execute("""
            INSERT INTO leads (name, phone, email, company, service_needed, budget, timeline, status, priority, notes, preferred_language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead.get("name", "Unknown"),
                phone,
                lead.get("email", ""),
                lead.get("company", ""),
                lead.get("service_needed", "Software Services"),
                lead.get("budget", "Flexible"),
                lead.get("timeline", "Immediate"),
                lead.get("status", "NEW"),
                lead.get("priority", "MEDIUM"),
                lead.get("notes", ""),
                lead.get("preferred_language", "te-IN")
            ))
            inserted += 1

    conn.commit()
    conn.close()
    return inserted, updated


def update_lead(lead_id: int, updates: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []
    for k, v in updates.items():
        if k in ["name", "phone", "email", "company", "service_needed", "budget", "timeline", "status", "priority", "notes", "preferred_language"]:
            fields.append(f"{k} = ?")
            values.append(v)

    if not fields:
        conn.close()
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(lead_id)

    query = f"UPDATE leads SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def delete_lead(lead_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


# ---------------- CALLS & TRANSCRIPTS ----------------

def save_call_record(call_data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO calls (
        lead_id, call_type, phone_number, duration_seconds, status,
        summary, sentiment, deal_stage, extracted_budget, extracted_timeline,
        extracted_requirements, objections_raised, action_items, transcript
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        call_data.get("lead_id"),
        call_data.get("call_type", "web"),
        call_data.get("phone_number", ""),
        call_data.get("duration_seconds", 0),
        call_data.get("status", "completed"),
        call_data.get("summary", ""),
        call_data.get("sentiment", "neutral"),
        call_data.get("deal_stage", "qualifying"),
        call_data.get("extracted_budget", ""),
        call_data.get("extracted_timeline", ""),
        call_data.get("extracted_requirements", ""),
        call_data.get("objections_raised", ""),
        call_data.get("action_items", ""),
        call_data.get("transcript", "")
    ))
    call_id = cursor.lastrowid

    # If lead_id is attached, update lead with call summary and status
    lead_id = call_data.get("lead_id")
    deal_stage = call_data.get("deal_stage", "qualifying")
    if lead_id:
        status_mapping = {
            "closed_won": "CLOSED_WON",
            "demo_scheduled": "DEMO_BOOKED",
            "qualified": "QUALIFIED",
            "follow_up": "CONTACTED",
            "lost": "LOST"
        }
        new_status = status_mapping.get(deal_stage.lower() if deal_stage else "", None)

        cursor.execute("""
        UPDATE leads
        SET status = COALESCE(?, status),
            budget = COALESCE(NULLIF(?, ''), budget),
            timeline = COALESCE(NULLIF(?, ''), timeline),
            service_needed = COALESCE(NULLIF(?, ''), service_needed),
            last_call_summary = ?,
            last_call_stage = ?,
            last_call_sentiment = ?,
            objections_noted = ?,
            action_items = ?,
            last_called_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            new_status,
            call_data.get("extracted_budget", ""),
            call_data.get("extracted_timeline", ""),
            call_data.get("extracted_requirements", ""),
            call_data.get("summary", ""),
            deal_stage,
            call_data.get("sentiment", "neutral"),
            call_data.get("objections_raised", ""),
            call_data.get("action_items", ""),
            lead_id
        ))

    conn.commit()
    conn.close()
    return call_id


def get_call_history(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.*, l.name as lead_name, l.company as lead_company
    FROM calls c
    LEFT JOIN leads l ON c.lead_id = l.id
    ORDER BY c.created_at DESC
    LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_call_by_id(call_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.*, l.name as lead_name, l.company as lead_company, l.phone as lead_phone
    FROM calls c
    LEFT JOIN leads l ON c.lead_id = l.id
    WHERE c.id = ?
    """, (call_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_calls_for_lead(lead_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM calls WHERE lead_id = ? ORDER BY created_at DESC
    """, (lead_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ---------------- COMPANY PROFILE & SETTINGS ----------------

def get_company_profile() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


def update_company_profile(data: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE company_profile
    SET agency_name = ?,
        tagline = ?,
        services_offered = ?,
        pricing_details = ?,
        preferred_language = ?,
        tts_voice = ?,
        sales_pitch = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = 1
    """, (
        data.get("agency_name", "S P Associates Software Company"),
        data.get("tagline", ""),
        data.get("services_offered", "[]"),
        data.get("pricing_details", ""),
        data.get("preferred_language", "te-IN"),
        data.get("tts_voice", "kavitha_te_conversation"),
        data.get("sales_pitch", "")
    ))
    conn.commit()
    conn.close()
    return True


# ---------------- DEVELOPER API KEYS & BILLING ----------------

import uuid
import secrets

def get_all_api_keys() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_primary_api_key() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE status = 'active' ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    # If no key exists, auto-seed one
    return create_api_key("Production Key", "developer@spassociates.com", "S P Associates Software Company", "Business Growth", 2500.0)


def get_api_key_by_token(token: str) -> Optional[Dict[str, Any]]:
    clean_token = token.strip()
    if clean_token.startswith("Bearer "):
        clean_token = clean_token[7:].strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE api_key = ? AND status = 'active'", (clean_token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_api_key(
    key_name: str,
    user_email: str,
    company_name: str = "Enterprise Client",
    plan_tier: str = "Developer Starter",
    initial_credits: float = 500.0
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    token = f"lc_live_{secrets.token_hex(16)}"
    rate = 4.0 if "Enterprise" in plan_tier else (4.5 if "Growth" in plan_tier else 5.0)

    cursor.execute("""
    INSERT INTO api_keys (key_name, user_email, company_name, api_key, plan_tier, credits_inr, rate_per_min, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
    """, (key_name, user_email, company_name, token, plan_tier, initial_credits, rate))
    key_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    new_key = dict(cursor.fetchone())
    conn.close()
    return new_key


def revoke_api_key(key_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE api_keys SET status = 'revoked', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()
    return True


def deduct_api_credits(token: str, duration_seconds: int) -> Dict[str, Any]:
    """
    Deducts talk-time credits based on connected duration (rounded up to nearest half minute, min 30s).
    """
    key_data = get_api_key_by_token(token)
    if not key_data:
        return {"success": False, "error": "Invalid or revoked API Key"}

    minutes = max(0.5, round(duration_seconds / 60.0, 2))
    rate = key_data.get("rate_per_min", 5.0)
    charge = round(minutes * rate, 2)

    current_balance = key_data.get("credits_inr", 0.0)
    new_balance = max(0.0, current_balance - charge)
    total_calls = key_data.get("total_calls", 0) + 1
    total_minutes = round(key_data.get("total_minutes", 0.0) + minutes, 2)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE api_keys
    SET credits_inr = ?, total_calls = ?, total_minutes = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (new_balance, total_calls, total_minutes, key_data["id"]))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "charged_inr": charge,
        "minutes_billed": minutes,
        "remaining_credits_inr": new_balance,
        "total_calls": total_calls
    }


def create_billing_order(
    api_key_id: int,
    plan_name: str,
    amount_inr: float,
    payment_method: str = "Instant UPI / Razorpay",
    customer_email: str = ""
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    order_id = f"ORD_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(4).upper()}"
    invoice_number = f"INV-SPA-{secrets.token_hex(3).upper()}"
    rate = 5.0
    if amount_inr >= 14999:
        rate = 3.75
    elif amount_inr >= 4999:
        rate = 4.16
    minutes_credited = round(amount_inr / rate, 1)

    cursor.execute("""
    INSERT INTO api_billing_orders (
        api_key_id, order_id, plan_name, amount_inr, minutes_credited,
        payment_method, payment_status, customer_email, invoice_number
    )
    VALUES (?, ?, ?, ?, ?, ?, 'success', ?, ?)
    """, (api_key_id, order_id, plan_name, amount_inr, minutes_credited, payment_method, customer_email, invoice_number))
    order_db_id = cursor.lastrowid

    # Credit the balance to the selected API key
    cursor.execute("""
    UPDATE api_keys
    SET credits_inr = credits_inr + ?,
        plan_tier = ?,
        rate_per_min = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (amount_inr, plan_name, rate, api_key_id))

    conn.commit()
    cursor.execute("SELECT * FROM api_billing_orders WHERE id = ?", (order_db_id,))
    order_row = dict(cursor.fetchone())
    conn.close()

    return order_row


def get_billing_orders() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_billing_orders ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


