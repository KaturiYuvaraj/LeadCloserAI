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

