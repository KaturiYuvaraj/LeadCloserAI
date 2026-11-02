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
        ("preferred_language", "TEXT DEFAULT 'te-IN'"),
        ("source", "TEXT DEFAULT 'manual'"),
        ("designation", "TEXT"),
        ("industry", "TEXT"),
        ("location", "TEXT"),
        ("website", "TEXT"),
        ("enrichment_data", "TEXT")
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
        recording_url TEXT,
        call_sid TEXT,
        disposition TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE SET NULL
    );
    """)

    cursor.execute("PRAGMA table_info(calls)")
    calls_cols = [col[1] for col in cursor.fetchall()]
    new_call_cols = [
        ("recording_url", "TEXT"),
        ("call_sid", "TEXT"),
        ("disposition", "TEXT")
    ]
    for c_name, c_type in new_call_cols:
        if c_name not in calls_cols:
            cursor.execute(f"ALTER TABLE calls ADD COLUMN {c_name} {c_type}")

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

    # Provider Integration Settings Table (Outpero Multi-Provider Architecture)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_settings (
        provider_type TEXT NOT NULL,
        provider_name TEXT NOT NULL,
        is_enabled BOOLEAN DEFAULT 1,
        is_configured BOOLEAN DEFAULT 0,
        config_json TEXT DEFAULT '{}',
        last_tested_at TIMESTAMP,
        test_status TEXT DEFAULT 'untested',
        test_message TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (provider_type, provider_name)
    );
    """)

    # Provider Credit Usage Logs (Protects Apollo/Apify Daily Limits)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT NOT NULL,
        operation TEXT NOT NULL,
        credits_used REAL DEFAULT 1.0,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # AI Employees Management Table (Module 6)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        description TEXT,
        language TEXT DEFAULT 'te-IN',
        voice_speaker TEXT DEFAULT 'kavitha_te_conversation',
        greeting TEXT NOT NULL,
        calling_objective TEXT,
        system_prompt TEXT NOT NULL,
        sales_script TEXT,
        qualification_questions TEXT,
        knowledge_base TEXT,
        working_hours TEXT DEFAULT '09:00 - 19:00',
        max_call_duration_seconds INTEGER DEFAULT 600,
        status TEXT DEFAULT 'draft',
        is_active BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed 5 specialized AI Sales Employees if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM ai_employees")
    if cursor.fetchone()["count"] == 0:
        seed_employees = [
            (
                "S P Senior Closer (Default)",
                "General Business Development Specialist",
                "Flagship multilingual sales closer for S P Associates software solutions.",
                "te-IN",
                "kavitha_te_conversation",
                "నమస్కారం అండి! నేను S P Associates Software Company నుండి మాట్లాడుతున్నాను. మీ వ్యాపారానికి కస్టమ్ వెబ్‌సైట్ లేదా మొబైల్ యాప్ అవసరం ఉందా అండి?",
                "Qualify client software needs and book a 10-minute live demo.",
                "You are a Senior Sales Closer at S P Associates Software Company. Qualify software requirements, answer questions, handle objections, and close with a live Zoom demo.",
                "Introduce -> Discover Need -> Match Services -> Address Budget/Timeline -> Book Demo",
                "1. Do you need a web app or mobile app?\n2. What is your estimated timeline?\n3. Who is your target customer?",
                "S P Associates builds custom websites, Android/iOS apps, billing software, and AI voice automation systems with flexible milestone payments.",
                "09:00 - 19:00",
                600,
                "active",
                1
            ),
            (
                "Priya - Web & SaaS Closer",
                "Website & Web Application Sales Specialist",
                "Focused on pitching modern responsive websites, SaaS web portals, and e-commerce stores.",
                "te-IN",
                "kavitha_te_conversation",
                "నమస్కారం అండి! మీ బిజినెస్‌కి ఆన్‌లైన్ వెబ్‌సైట్ లేదా ఈ-కామర్స్ పోర్టల్ డెవలప్‌మెంట్ కోసం S P Associates నుండి కాల్ చేస్తున్నాను.",
                "Close custom website and web app development deals.",
                "You are Priya, Web & SaaS Sales Specialist at S P Associates Software Company. Emphasize fast load times, Google SEO ranking, and online sales conversions.",
                "Highlight web design portfolio -> Offer free 5-minute technical audit -> Schedule demo.",
                "1. Do you already have an existing website?\n2. Do you need online payment gateway integration?",
                "We use React, Next.js, and Node.js for ultra-fast, modern web applications.",
                "09:30 - 18:30",
                600,
                "approved",
                0
            ),
            (
                "Rahul - Mobile App Specialist",
                "iOS & Android Mobile Applications Consultant",
                "Specializes in custom mobile apps, customer ordering apps, and delivery tracking.",
                "hi-IN",
                "pooja",
                "नमस्ते सर! मैं S P Associates Software Company से राहुल बात कर रहा हूँ। क्या आपकी कंपनी के लिए कोई मोबाइल ऐप बनाने का प्लान है?",
                "Qualify mobile application requirements and estimate project milestones.",
                "You are Rahul, Mobile App Solutions Specialist at S P Associates Software Company. Discuss iOS, Android, and cross-platform Flutter/React Native solutions.",
                "Understand app features -> Explain playstore publication -> Propose starting package.",
                "1. Do you need Android or iOS or both?\n2. What core features do you need?",
                "Full-stack mobile app development with push notifications, maps, and Razorpay.",
                "10:00 - 19:00",
                600,
                "approved",
                0
            ),
            (
                "Arjun - AI Voice & Chatbot Closer",
                "AI Telephony & WhatsApp Automation Consultant",
                "Pitches automated AI phone calling agents and Meta WhatsApp business messaging.",
                "en-IN",
                "tarun",
                "Hello! This is Arjun from S P Associates Software Company. We help businesses automate customer sales calls and WhatsApp replies using native Indian AI.",
                "Deploy AI autonomous caller systems for prospective businesses.",
                "You are Arjun, AI Voice Automation Consultant at S P Associates Software Company. Explain how AI telephone agents reduce operational costs by 70%.",
                "Demonstrate AI call handling -> Share ROI metrics -> Offer pilot trial.",
                "1. How many incoming or outgoing customer calls do you handle daily?",
                "Our AI caller speaks Telugu, Hindi, and English natively with Exotel telephony integration.",
                "09:00 - 20:00",
                900,
                "approved",
                0
            ),
            (
                "Venkatesh - ERP & Billing Specialist",
                "Retail & Wholesale ERP Software Consultant",
                "Specialized in inventory, POS billing, GST invoicing, and accounting software.",
                "te-IN",
                "kavitha_te_conversation",
                "నమస్కారం అండి! మీ రిటైల్ లేదా డిస్ట్రిబ్యూషన్ బిజినెస్‌కి జీఎస్టీ బిల్లింగ్ మరియు ఇన్వెంటరీ సాఫ్ట్‌వేర్ గురించి S P Associates నుండి మాట్లాడుతున్నాను.",
                "Demonstrate retail ERP billing software and schedule onsite or Zoom demo.",
                "You are Venkatesh, ERP Solutions Consultant. Emphasize GST compliance, barcode scanner support, and daily sales reports on mobile.",
                "Assess inventory complexity -> Explain mobile reporting -> Offer 7-day free trial.",
                "1. Do you need barcode scanning and thermal receipt printing?",
                "Cloud-synced billing software works offline and online.",
                "09:00 - 19:00",
                600,
                "approved",
                0
            )
        ]
        cursor.executemany("""
        INSERT INTO ai_employees (
            name, role, description, language, voice_speaker, greeting,
            calling_objective, system_prompt, sales_script, qualification_questions,
            knowledge_base, working_hours, max_call_duration_seconds, status, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_employees)
    # Campaigns Table (Module 7: Persistent Multi-Channel Campaigns)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        employee_id INTEGER DEFAULT 1,
        lead_ids_json TEXT DEFAULT '[]',
        mode TEXT DEFAULT 'telephony',
        status TEXT DEFAULT 'draft',
        total_leads INTEGER DEFAULT 0,
        completed_leads INTEGER DEFAULT 0,
        max_concurrency INTEGER DEFAULT 3,
        retry_attempts INTEGER DEFAULT 2,
        results_json TEXT DEFAULT '{}',
        logs_json TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES ai_employees (id) ON DELETE SET NULL
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
    enrichment = lead_data.get("enrichment_data")
    if isinstance(enrichment, dict):
        enrichment = json.dumps(enrichment, ensure_ascii=False)

    cursor.execute("""
    INSERT INTO leads (
        name, phone, email, company, service_needed, budget, timeline, status, priority, notes, preferred_language,
        source, designation, industry, location, website, enrichment_data
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        lead_data.get("preferred_language", "te-IN"),
        lead_data.get("source", "manual"),
        lead_data.get("designation", ""),
        lead_data.get("industry", ""),
        lead_data.get("location", ""),
        lead_data.get("website", ""),
        enrichment or ""
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
        if k in ["name", "phone", "email", "company", "service_needed", "budget", "timeline", "status", "priority", "notes", "preferred_language", "source", "designation", "industry", "location", "website", "enrichment_data", "action_items", "last_call_summary", "last_call_stage", "last_call_sentiment", "objections_noted"]:
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
        extracted_requirements, objections_raised, action_items, transcript,
        recording_url, call_sid, disposition
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        call_data.get("transcript", ""),
        call_data.get("recording_url", ""),
        call_data.get("call_sid", ""),
        call_data.get("disposition", call_data.get("status", "completed"))
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


# ---------------- PROVIDER INTEGRATION SETTINGS ----------------

def get_all_provider_settings() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM provider_settings ORDER BY provider_type, provider_name")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_provider_setting(provider_type: str, provider_name: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM provider_settings WHERE provider_type = ? AND provider_name = ?",
        (provider_type, provider_name)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_provider_setting(
    provider_type: str,
    provider_name: str,
    is_enabled: bool,
    is_configured: bool,
    config: Dict[str, Any],
    test_status: Optional[str] = None,
    test_message: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    config_str = json.dumps(config) if isinstance(config, dict) else str(config)

    cursor.execute("""
    INSERT INTO provider_settings (provider_type, provider_name, is_enabled, is_configured, config_json, test_status, test_message, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(provider_type, provider_name) DO UPDATE SET
        is_enabled = excluded.is_enabled,
        is_configured = excluded.is_configured,
        config_json = excluded.config_json,
        test_status = COALESCE(excluded.test_status, provider_settings.test_status),
        test_message = COALESCE(excluded.test_message, provider_settings.test_message),
        updated_at = CURRENT_TIMESTAMP
    """, (
        provider_type,
        provider_name,
        1 if is_enabled else 0,
        1 if is_configured else 0,
        config_str,
        test_status or "untested",
        test_message or ""
    ))
    conn.commit()
    conn.close()
    return get_provider_setting(provider_type, provider_name) or {}


def record_provider_test_result(
    provider_type: str,
    provider_name: str,
    status: str,
    message: str
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE provider_settings
    SET test_status = ?,
        test_message = ?,
        last_tested_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE provider_type = ? AND provider_name = ?
    """, (status, message, provider_type, provider_name))
    conn.commit()
    conn.close()




# ---------------- LEAD ENRICHMENT & PROVIDER USAGE HELPERS ----------------

def update_lead_enrichment(lead_id: int, enrichment: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> bool:
    """
    Update a lead with enriched organization details, tech stack, and intelligence.
    """
    conn = get_connection()
    cursor = conn.cursor()
    enrichment_json = json.dumps(enrichment, ensure_ascii=False) if isinstance(enrichment, dict) else str(enrichment)

    fields = ["enrichment_data = ?", "updated_at = CURRENT_TIMESTAMP"]
    values = [enrichment_json]

    if extra:
        for col in ["industry", "website", "designation", "location", "company", "email"]:
            if extra.get(col):
                fields.append(f"{col} = COALESCE(NULLIF(?, ''), {col})")
                values.append(extra[col])

    values.append(lead_id)
    query = f"UPDATE leads SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def get_daily_provider_usage(provider_name: str) -> float:
    """
    Calculate total credits used by a provider today.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(credits_used), 0.0) as total_credits
        FROM provider_usage_logs
        WHERE provider_name = ?
          AND date(timestamp) = date('now')
    """, (provider_name,))
    row = cursor.fetchone()
    conn.close()
    return float(row["total_credits"]) if row else 0.0


def record_provider_usage(provider_name: str, operation: str, credits_used: float = 1.0, details: str = ""):
    """
    Record third-party API provider credit usage to enforce daily limits.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO provider_usage_logs (provider_name, operation, credits_used, details)
        VALUES (?, ?, ?, ?)
    """, (provider_name, operation, credits_used, details))
    conn.commit()
    conn.close()


def update_call_recording_by_sid(call_sid: str, recording_url: str) -> bool:
    """Update call record with telephony carrier recording URL."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE calls
        SET recording_url = ?
        WHERE call_sid = ?
    """, (recording_url, call_sid))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def update_call_status_by_sid(call_sid: str, status: str, duration: int = 0) -> bool:
    """Update call status and disposition based on telephony callbacks."""
    conn = get_connection()
    cursor = conn.cursor()
    fields = ["status = ?", "disposition = ?"]
    values = [status, status]
    if duration > 0:
        fields.append("duration_seconds = ?")
        values.append(duration)
    values.append(call_sid)
    cursor.execute(f"UPDATE calls SET {', '.join(fields)} WHERE call_sid = ?", values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


# ---------------- AI EMPLOYEES CRUD (MODULE 6) ----------------

def get_all_ai_employees() -> List[Dict[str, Any]]:
    """Fetch all configured AI employees."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_employees ORDER BY is_active DESC, updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_ai_employee_by_id(emp_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a specific AI employee by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_employees WHERE id = ?", (emp_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_ai_employee() -> Optional[Dict[str, Any]]:
    """Fetch the currently active AI sales employee."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_employees WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM ai_employees ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_ai_employee(data: Dict[str, Any]) -> int:
    """Create a new AI employee (draft or approved)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ai_employees (
        name, role, description, language, voice_speaker, greeting,
        calling_objective, system_prompt, sales_script, qualification_questions,
        knowledge_base, working_hours, max_call_duration_seconds, status, is_active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "New AI Sales Agent"),
        data.get("role", "Sales Specialist"),
        data.get("description", ""),
        data.get("language", "te-IN"),
        data.get("voice_speaker", "kavitha_te_conversation"),
        data.get("greeting", "Hello! I am calling from S P Associates Software Company."),
        data.get("calling_objective", "Qualify requirements and schedule demo."),
        data.get("system_prompt", "You are a professional sales closer."),
        data.get("sales_script", ""),
        data.get("qualification_questions", ""),
        data.get("knowledge_base", ""),
        data.get("working_hours", "09:00 - 19:00"),
        int(data.get("max_call_duration_seconds", 600)),
        data.get("status", "draft"),
        1 if data.get("is_active") else 0
    ))
    emp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return emp_id


def update_ai_employee(emp_id: int, updates: Dict[str, Any]) -> bool:
    """Update an AI employee's profile, script, or status."""
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    allowed = [
        "name", "role", "description", "language", "voice_speaker", "greeting",
        "calling_objective", "system_prompt", "sales_script", "qualification_questions",
        "knowledge_base", "working_hours", "max_call_duration_seconds", "status"
    ]
    for k, v in updates.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)

    if not fields:
        conn.close()
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(emp_id)
    query = f"UPDATE ai_employees SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def set_active_ai_employee(emp_id: int) -> bool:
    """Set a specific AI employee as active, setting all others to inactive."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE ai_employees SET is_active = 0")
    cursor.execute("UPDATE ai_employees SET is_active = 1, status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (emp_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def delete_ai_employee(emp_id: int) -> bool:
    """Delete an AI employee if not the only active one."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ai_employees WHERE id = ? AND is_active = 0", (emp_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


# ---------------- CAMPAIGN MANAGEMENT CRUD (MODULE 7) ----------------

def create_campaign(data: Dict[str, Any]) -> int:
    """Create and persist a new sales campaign."""
    conn = get_connection()
    cursor = conn.cursor()
    lead_ids = data.get("lead_ids", [])
    lead_ids_json = json.dumps(lead_ids) if isinstance(lead_ids, list) else str(lead_ids)

    cursor.execute("""
    INSERT INTO campaigns (
        name, description, employee_id, lead_ids_json, mode, status,
        total_leads, completed_leads, max_concurrency, retry_attempts, results_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "New Outbound Campaign"),
        data.get("description", ""),
        data.get("employee_id", 1),
        lead_ids_json,
        data.get("mode", "telephony"),
        data.get("status", "draft"),
        len(lead_ids) if isinstance(lead_ids, list) else int(data.get("total_leads", 0)),
        0,
        int(data.get("max_concurrency", 3)),
        int(data.get("retry_attempts", 2)),
        json.dumps(data.get("results", {"demo_scheduled": 0, "closed_won": 0, "follow_up": 0, "lost": 0, "failed": 0}))
    ))
    camp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return camp_id


def get_all_campaigns() -> List[Dict[str, Any]]:
    """Fetch all persisted campaigns with progress metrics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns ORDER BY updated_at DESC")
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        try:
            d["lead_ids"] = json.loads(d.get("lead_ids_json") or "[]")
            d["results"] = json.loads(d.get("results_json") or "{}")
            d["logs"] = json.loads(d.get("logs_json") or "[]")
        except Exception:
            pass
        rows.append(d)
    conn.close()
    return rows


def get_campaign_by_id(camp_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single campaign by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (camp_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    d = dict(row)
    try:
        d["lead_ids"] = json.loads(d.get("lead_ids_json") or "[]")
        d["results"] = json.loads(d.get("results_json") or "{}")
        d["logs"] = json.loads(d.get("logs_json") or "[]")
    except Exception:
        pass
    conn.close()
    return d


def update_campaign_status(camp_id: int, status: str, completed: Optional[int] = None, results: Optional[Dict[str, Any]] = None, log_entry: Optional[Dict[str, Any]] = None) -> bool:
    """Update campaign status, completed leads counter, results, and append logs."""
    conn = get_connection()
    cursor = conn.cursor()

    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values = [status]

    if completed is not None:
        fields.append("completed_leads = ?")
        values.append(completed)

    if results is not None:
        fields.append("results_json = ?")
        values.append(json.dumps(results))

    if log_entry is not None:
        cursor.execute("SELECT logs_json FROM campaigns WHERE id = ?", (camp_id,))
        cur_row = cursor.fetchone()
        cur_logs = []
        if cur_row and cur_row["logs_json"]:
            try:
                cur_logs = json.loads(cur_row["logs_json"])
            except Exception:
                pass
        cur_logs.append(log_entry)
        if len(cur_logs) > 100:
            cur_logs = cur_logs[-100:]
        fields.append("logs_json = ?")
        values.append(json.dumps(cur_logs))

    values.append(camp_id)
    query = f"UPDATE campaigns SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success
