# 🎙️ LeadCloserAI: Multilingual Autonomous AI Voice Caller & Lead Closing CRM

An autonomous, enterprise-grade AI Voice Calling & Deal Closing CRM built for Software, IT, Real Estate, Healthcare, Education, and Agency Businesses representing **S P Associates Software Company**. 

It conducts fluent, human-like conversations in **Telugu**, **Hindi**, and **Indian English**, intelligently matches customer language in real time, handles price and timeline objections, schedules project demos, and automatically saves executive post-call intelligence and summaries in English.

Powered by **Sarvam AI** (`sarvam-105b-conversations`, `bulbul:v4-flash`, `saaras:v3`), **FastAPI**, **SQLAlchemy 2.0**, and **PostgreSQL / SQLite**.

---

## 🌟 Key Capabilities

### 1. 🎯 Explainable Lead Scoring System (Phase 7)
- **Deterministic 0–100 Qualification**: Every lead receives an explainable qualification score across 5 transparent factors:
  1. **Budget & Commercial Viability** (0–25 pts): Quantified budget thresholds (₹50k–₹2L+: 25 pts, ₹25k–₹50k: 18 pts, <₹25k: 10 pts, undefined: 5 pts).
  2. **Need & Timeline Urgency** (0–20 pts): Immediate / < 1 week (20 pts), 1–4 weeks (15 pts), 1–3 months (10 pts), casual/exploratory (4 pts).
  3. **Service Alignment** (0–20 pts): Direct match for core multilingual AI voice & sales closing (20 pts), CRM/automation (12 pts), general (5 pts).
  4. **Engagement & Call Outcome** (0–25 pts): Demo requested / callback scheduled (25 pts), qualified discussion (18 pts), connected (10 pts), DND/disqualified (0 pts).
  5. **Decision Maker Fit** (0–10 pts): C-Level / Founder / Managing Director (10 pts), Senior Manager / Head (7 pts), operational contact (3 pts).
- **Three Core Categories**:
  - **HOT (80–100)**: Immediate sales closing follow-up, assigned to human rep.
  - **WARM (50–79)**: Enrolled in multilingual AI voice nurturing sequences.
  - **COLD (<50)**: Low priority or educational drip messaging.
- **Explainable Factor Breakdowns**: Each factor includes point contributions, max points, and human-readable reasoning strings.

### 2. 🔐 Enterprise Authentication & Role-Based Access Control (Phase 3)
- **Self-Service Registration** (`POST /api/auth/register`): Creates customer accounts and initial `owner` user with strict password validation (min 8 chars, alphanumeric).
- **Login Rate-Limiting**: Thread-safe sliding window limiter blocks brute force attacks (max 5 failed attempts per IP/email in a 5-minute window, returns HTTP 429).
- **Role Hierarchy**: Strict permission gates:
  - `owner` (full organizational and billing control)
  - `admin` (team management, campaigns, settings)
  - `manager` (campaign configuration, employee management, CRM review)
  - `salesperson` (CRM leads, call dispatch, callbacks)
  - `member` (view-only operations)
- **Tenant Isolation**: Every database query scopes `account_id` foreign keys, preventing cross-tenant access.

### 3. 📊 Excel & CSV Sheet Lead Ingestion & Export
- **Spreadsheet Upload:** Upload `.xlsx`, `.xls`, or `.csv` files containing customer leads with formula-injection sanitization (`sanitize_for_spreadsheet`).
- **Smart Column Auto-Detection:** Automatically maps fields for Name, Phone Number, Company, Service Needed, Budget, Timeline, Preferred Language, and Notes.
- **Sample Template:** Download a pre-formatted Excel template (`leads_template.xlsx`) directly from the UI.
- **Duplicate Prevention:** Existing phone numbers are automatically detected and updated without creating duplicate entries.

### 4. ⚡ Autonomous Auto-Calling Campaigns (Phase 10)
- **Persistent Campaign Model:** Database-backed campaigns (`Campaign`) supporting name, description, employee assignment, lead lists, concurrency limits, and retry policies.
- **Restart-Safe Outbound Queue:** Persistent queue (`call_jobs` table via `voice_agent/dialer.py`), enforcing TRAI calling hours (9 AM–7 PM IST), DND screening, and weekly call frequency caps.
- **Campaign Controls:** Real-time Pause, Resume, Stop, and Concurrency controls from the dashboard.

### 5. 🤖 Configurable AI Employees (Phase 9)
- **Persona Customization:** Configure Telugu, Hindi, and Indian English AI sales reps with distinct tones, greetings, offers, and voice gender.
- **Instant Duplication:** Clone any employee persona with a single click (`POST /api/employees/{id}/duplicate`) for rapid A/B testing.
- **Voice Auditioning:** In-browser test synthesis (`POST /api/employees/{id}/test`) plays sample greetings via Sarvam TTS before deployment.

### 6. 🗣️ Multilingual Conversational Engine
- **Automatic Language Matching:** Seamlessly detects and answers in the customer's preferred language (**Telugu**, **Hindi**, or **English**) or immediately switches when asked.
- **Natural Human Turn-Taking & Pacing:**
  - Web Audio API Voice Activity Detection (VAD) with an adaptive silence endpoint detector.
  - Mic echo suppression during AI playback.
  - Empathetic acknowledgement openers before presenting solutions (*"సరేనండి, అర్థమైంది..."*, *"जी बिल्कुल सर, समझ गया..."*, *"Got it, absolutely..."*).
  - Short, focused responses (1-2 sentences) ending with a clear call-to-action.

### 7. 📈 Zero-Fake-Data Analytics & Multi-Dimensional Filtering (Phase 17)
- **100% Real Database Metrics:** Executive KPIs, conversion funnels, sentiment distributions, and objection analytics computed purely from real database rows (no synthetic mock fallbacks).
- **Multi-Dimensional Filters:** Filter analytics by `date_from`, `date_to`, `source`, and `campaign_id`.

---

## 📁 Repository Structure

```
LeadCloserAI/
├── .gitignore                      # Git ignore rules (protects API keys & virtualenv)
├── README.md                       # Comprehensive documentation
├── run_caller.bat                  # One-click Windows startup script
└── telugu-ai-caller/
    ├── .env.example                # Sample environment configuration
    ├── requirements.txt            # Python dependencies
    ├── main.py                     # FastAPI application, WebSockets & REST routes
    ├── database.py                 # SQLite/PostgreSQL CRM for Leads, Calls, Deals & Agency Profile
    ├── config.py                   # Configuration and environment loader
    ├── core/
    │   ├── auth.py                 # JWT, PBKDF2 hashing, login rate limiting, role hierarchy
    │   ├── db.py                   # SQLAlchemy 2.0 engine, PostgreSQL & SQLite support
    │   └── web.py                  # Jinja2 template environment
    ├── models/                     # SQLAlchemy models with tenant account_id scoping
    │   ├── account.py              # Account tenant model
    │   ├── user.py                 # User & team model
    │   ├── lead.py                 # CRM Lead model
    │   ├── call.py                 # Call records & transcripts
    │   ├── campaign.py             # Persistent Campaign model
    │   └── employee.py             # AI Employee persona model
    ├── services/
    │   ├── lead_scoring.py         # Explainable 0-100 qualification engine (5 transparent factors)
    │   ├── sarvam_service.py       # Sarvam STT, TTS, and 105B LLM async client
    │   ├── sales_agent.py          # Sales dialogue engine, objection handler & extractor
    │   ├── campaign_service.py     # Background auto-calling campaign engine
    │   ├── excel_service.py        # Excel/CSV parser and summary exporter with formula sanitization
    │   └── audio_processor.py      # Audio conversion (PCM, WAV, mu-law)
    ├── routers/
    │   ├── auth.py                 # Self-registration, login, team management, rate limiting
    │   ├── leads.py                # Leads CRUD, search, pagination, explainable scoring
    │   ├── campaigns.py            # Persistent campaign management and queue dispatch
    │   ├── employees.py            # AI employee personas, duplication, voice audition
    │   └── calls.py                # Call records and filtered analytics overview
    ├── static/
    │   ├── css/style.css           # Floating glassmorphism navbar & clean CRM dashboard styles
    │   └── js/
    │       ├── app.js              # CRM 11-view UI state, Lucide icons, lead selection
    │       └── call_client.js      # Web Audio mic streaming and turn-taking VAD
    ├── templates/
    │   ├── index.html              # Floating glassmorphism landing showcase
    │   ├── crm.html                # Unified 11-view CRM Station with Lucide icons
    │   └── login.html              # Secure team authentication interface
    └── tests/
        ├── test_lead_scoring_and_production_improvements.py # Scoring, registration, rate limiting
        ├── test_multi_tenant_security.py # Tenant data isolation tests
        ├── test_developer_api.py   # Tests API key generation, billing & call dispatch
        ├── test_english_summaries.py # Verifies 100% English CRM summary storage
        ├── test_pacing_and_turn_taking.py # Verifies conversational timing & human pacing
        └── test_campaign_and_excel.py # Tests Excel import/export & auto campaigns
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/KaturiYuvaraj/LeadCloserAI.git
cd LeadCloserAI
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` inside `telugu-ai-caller/`:
```bash
cp telugu-ai-caller/.env.example telugu-ai-caller/.env
```
Open `telugu-ai-caller/.env` and insert your credentials:
```env
APP_ENV=development
SECRET_KEY=your-secure-random-jwt-signing-key
SARVAM_API_KEY=your_sarvam_api_key_here
```

### 3. Setup Virtual Environment & Install Dependencies
```bash
cd telugu-ai-caller
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Run the Application
```bash
python main.py
```
Or simply double-click `run_caller.bat` on Windows.

Open your browser at:
👉 **http://localhost:8000**

---

## 🧪 Running the Automated Test Suite

Run pytest to verify the full suite of unit, integration, and security tests:

```bash
cd telugu-ai-caller
.\venv\Scripts\pytest -v
```

All 119 unit tests pass automatically with zero external network dependencies.

---

## 🛡️ License

Developed for **S P Associates Software Company**. All rights reserved.
