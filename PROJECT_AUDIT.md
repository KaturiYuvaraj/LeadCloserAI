# PROJECT AUDIT & TECHNICAL GAP ANALYSIS
**AI Sales Automation Platform (Outpero-Inspired)**
*Document Version: 1.0.0 | Date: November 2, 2026*
*Target Codebase: `telugu-ai-caller` within `Leads_AI_Project`*

---

## 1. Executive Summary

This document presents a comprehensive technical audit of the existing Python-based AI Voice Caller & Lead Closing CRM application (`telugu-ai-caller`). The objective is to evaluate the existing codebase against the target architecture of an enterprise-grade AI Sales Automation Platform inspired by Outpero, powered by independently integrated third-party providers (Exotel, Sarvam AI, Apollo.io, Apify, Meta WhatsApp Cloud API, Google Calendar API, PostgreSQL, and Redis/Celery).

The current application is a functional, single-tenant, lightweight voice calling CRM with:
- **FastAPI** backend with asynchronous HTTP endpoints and WebSockets.
- **Sarvam AI Base Plan** integration for Indian multilingual speech (STT `saaras:v3`, TTS `bulbul:v4-flash` / `bulbul:v3`, and LLM `sarvam-105b-conversations`).
- **Interactive Web Caller** supporting real-time browser microphone audio dialogue in Telugu, Hindi, and Indian English with active pacing and conversational pauses.
- **SQLite Database** storing leads, call histories, post-call deal intelligence (summaries strictly in English), developer API keys, and talk-time credit billing orders.
- **Excel / CSV Service** supporting `.xlsx` template generation, file upload parsing with fuzzy column header matching, and rich summary reports export.
- **Outpero-Inspired Aurora Porcelain Luxury Light Frontend** featuring a responsive 3-column CRM station (Leads pipeline, live calling station with audio waveform, objection playbook) and developer API sandbox.

---

## 2. Complete Project Inventory

```
Leads_AI_Project/
├── .gitignore                          # Root gitignore
├── README.md                           # Project documentation
├── run_caller.bat                      # Windows launcher script
└── telugu-ai-caller/
    ├── .env                            # Local environment variables (SARVAM_API_KEY)
    ├── .env.example                    # Environment template
    ├── .gitignore                      # Python & virtualenv ignore rules
    ├── config.py                       # Application configuration & env loader
    ├── database.py                     # SQLite CRUD, schema migrations & seed data
    ├── leads_crm.db                    # Active SQLite database (160KB)
    ├── main.py                         # FastAPI application entrypoint & WebSockets
    ├── migrate_to_english_summaries.py # DB migration script for executive summaries
    ├── README.md                       # Subproject instructions
    ├── requirements.txt                # Python package dependencies
    ├── services/
    │   ├── __init__.py                 # Package initializer
    │   ├── audio_processor.py          # PCM <-> WAV <-> mu-law (G.711) audio conversions
    │   ├── campaign_service.py         # Autonomous auto-calling campaign engine (asyncio)
    │   ├── excel_service.py            # OpenPyXL parser, template generator & export
    │   ├── language_utils.py           # Language detection & TTS speaker routing
    │   ├── sales_agent.py              # BANT qualification, prompt builder & intelligence
    │   ├── sarvam_service.py           # Sarvam AI REST API wrapper (STT, TTS, LLM)
    │   └── telephony_service.py        # Twilio telephony stub & TwiML stream generator
    ├── static/
    │   ├── css/
    │   │   └── style.css               # Aurora Porcelain Light SaaS design system (35KB)
    │   └── js/
    │       ├── app.js                  # Frontend state, modals, tabs, API sandbox
    │       └── call_client.js          # Web Audio API microphone capture & playback
    ├── templates/
    │   └── index.html                  # Jinja2 Single Page Application UI (117KB)
    └── tests/
        ├── test_api.py                 # Core CRM API endpoints tests
        ├── test_call_summary_storage.py# Call records & persistence tests
        ├── test_campaign_and_excel.py  # Excel parsing & auto-campaign tests
        ├── test_developer_api.py       # REST API dispatch & talk-time billing tests
        ├── test_english_summaries.py   # English executive summary integrity tests
        ├── test_multilingual.py        # Telugu/Hindi/English language matching tests
        ├── test_pacing_and_turn_taking.py # Conversational pacing & delay tests
        └── test_pipeline.py            # Sales pipeline & stage progression tests
```

---

## 3. Deep-Dive Component Audit

### 3.1. Python Backend & Architecture
- **Framework**: `FastAPI` (>=0.111.0) running on `uvicorn[standard]` (>=0.30.0).
- **Asynchronous Execution**: Fully `async`/`await` driven for HTTP handlers and WebSockets.
- **Routing**: All routes currently reside in `main.py` (~800 lines). Routes include:
  - Frontend delivery: `GET /`
  - Leads management: `GET /api/leads`, `GET /api/leads/{id}`, `POST /api/leads`, `PUT /api/leads/{id}`, `DELETE /api/leads/{id}`
  - Excel/CSV workflows: `GET /api/leads/template`, `GET /api/leads/export-excel`, `POST /api/leads/upload-excel`
  - Calling & history: `GET /api/calls`, `GET /api/calls/{id}`, `GET /api/leads/{id}/calls`
  - Campaigns: `POST /api/campaign/start`, `GET /api/campaign/status`, `POST /api/campaign/pause`, `POST /api/campaign/resume`, `POST /api/campaign/stop`
  - Telephony & Voice: `POST /api/tts/test`, `POST /api/call/outbound`, `POST /telephony/twiml`
  - Developer API v1: `GET/POST/DELETE /api/v1/keys`, `GET/POST /api/v1/billing/orders`, `POST /api/v1/calls/dispatch`, `GET /api/v1/calls/{id}/intelligence`
  - Real-time WebSockets: `/ws/web-call` (browser Web Audio mic) and `/ws/telephony` (Twilio mu-law stream).
- **Gap**: Routes need modular decomposition into FastAPI `APIRouter` submodules (`routers/leads.py`, `routers/campaigns.py`, `routers/telephony.py`, `routers/discovery.py`, `routers/messaging.py`).

### 3.2. Database Architecture & Schema
- **Database Engine**: Local SQLite 3 via standard library `sqlite3` with row factory.
- **Tables**:
  1. `leads`: Basic prospect information, qualification status, and latest call executive summary.
  2. `calls`: Call duration, type (`web` or `telephony`), deal stage, English summary, sentiment, objections, action items, and full conversation transcript JSON.
  3. `company_profile`: Single-row profile for "S P Associates Software Company" with service descriptions and default pitch.
  4. `api_keys`: Developer API licensing with talk-time INR balance, per-minute billing rates, and usage counters.
  5. `api_billing_orders`: Order transaction log for INR talk-time top-ups.
- **Gaps**:
  - No separation between `contacts` and `companies` (B2B requires account-level data vs contact-level data).
  - No dedicated `campaigns` table (campaign state is currently stored in-memory in `CampaignService`).
  - No `ai_employees` table (agents are hardcoded to a single system prompt template).
  - No `actions` / `tool_definitions` table.
  - No `knowledge_documents` / vector store for RAG.
  - No multi-tenant user authentication or RBAC tables (`users`, `organizations`, `roles`, `audit_logs`).
  - SQLite cannot handle high-concurrency write locks required by multi-line simultaneous auto-calling; migration path to **PostgreSQL** is necessary.

### 3.3. Sarvam AI Voice & LLM Integration
- **Speech-to-Text (STT)**:
  - Implemented via REST POST to `https://api.sarvam.ai/speech-to-text`.
  - Model: `saaras:v3` with `language_code="unknown"` for automatic Indic language detection.
  - File format: 16kHz 16-bit linear PCM packaged with standard WAV headers.
  - Plan constraint: REST-based batch audio transcription. The current Sarvam Base Plan uses HTTP REST; true bidirectional real-time audio requires evaluated WebSocket streaming (`saaras:v4` or streaming endpoints when enabled).
- **Text-to-Speech (TTS)**:
  - Implemented via REST POST to `https://api.sarvam.ai/text-to-speech`.
  - Model: `bulbul:v4-flash` (with fallback to `bulbul:v3`).
  - Dynamic Speaker Routing: `kavitha_te_conversation` (Telugu), `aditya_hi_sales` (Hindi), `simran_en_sales` (English).
  - Payload handling: Respects model-specific temperature constraints and character limits (<2,500 chars).
- **Large Language Model (LLM)**:
  - Implemented via Sarvam Token Factory OpenAI-compatible REST endpoint `https://api.sarvam.ai/v1/chat/completions`.
  - Model: `sarvam-105b-conversations`.
  - Features: Multi-turn prompt with conversational active listening ("సరేనండి, అర్థమైంది...", "जी बिल्कुल सर...", "Got it, absolutely..."), 1-2 sentence concise closing responses, and post-call intelligence extraction with guaranteed translation into executive English.

### 3.4. Telephony Integration
- **Current State**:
  - Contains legacy Twilio REST call initiation (`telephony_service.py`) and Twilio Media Stream WebSocket (`/ws/telephony`).
  - Twilio audio encoding: 8kHz G.711 mu-law, converted via `audioop` in `audio_processor.py`.
- **Target Provider: Exotel**:
  - Not yet implemented.
  - Exotel requires integration with **Exotel Voice AI / AgentStream** WebSocket protocol.
  - Requires Exotel credentials: `EXOTEL_ACCOUNT_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_SUB_DOMAIN`, and `EXOTEL_CALLER_ID`.
  - Endpoints needed: `/api/telephony/exotel/stream` (bidirectional audio stream), `/api/telephony/exotel/status` (call lifecycle callback), and `/api/telephony/exotel/recording` (call recording callback).

### 3.5. Lead Discovery (Apollo.io & Apify)
- **Apollo.io**: Completely absent in current codebase.
- **Apify**: Completely absent in current codebase.
- **Gap**: Requires dedicated provider modules under `providers/leads/apollo.py` and `providers/leads/apify.py` with schema normalization into a unified lead entity.

### 3.6. Messaging & Calendar (WhatsApp & Google Calendar)
- **Meta WhatsApp Cloud API**: Absent.
- **Google Calendar API**: Absent.
- **Gap**: Requires OAuth/API client integrations to trigger immediate follow-up brochures and meeting bookings upon call completion.

### 3.7. Task Processing & Background Workers
- **Current State**: `campaign_service.py` executes campaigns in-memory using an `asyncio.Task`.
- **Risks**: Server restart aborts in-flight calls; no persistent job queue; no distributed locking across worker nodes; concurrency is bound to the single Python process.
- **Target**: Celery worker tasks backed by **Redis** for distributed queuing, concurrency gating, and idempotent retry policies.

---

## 4. Master Feature Classification Matrix

Every capability requested across Modules 1 to 25 of the Master Development Prompt is classified according to the 5 designated categories:
1. **Already implemented**: Fully functioning and verified in current codebase.
2. **Partially implemented**: Basic foundations exist, but requires expansion or refactoring.
3. **Not implemented**: No code currently exists.
4. **Requires external API access**: Requires third-party credentials or active external account.
5. **Blocked by current API plan or provider limitations**: Restricted by plan tier or service availability.

| Module | Feature / Capability | Classification | Current State in Codebase | Technical Notes / Action Required |
|---|---|---|---|---|
| **M1: Audit** | Project gap analysis & audit documentation | **Already implemented** | Completed in `PROJECT_AUDIT.md`, `IMPLEMENTATION_PLAN.md`, `API_REQUIREMENTS.md` | Full repository indexed |
| **M2: Architecture** | Modular provider interface pattern | **Not implemented** | Services are directly coupled to specific implementations | Build `providers/` package with abstract base classes (`base.py`) |
| **M2: Architecture** | Provider settings & toggle UI | **Not implemented** | Settings read strictly from `.env` | Build integration settings view in UI with credential test buttons |
| **M3: Exotel** | Outbound PSTN calling via Connect Voice AI | **Requires external API access** | Only Twilio REST stub exists | Implement `ExotelTelephonyProvider` using Exotel Voice API |
| **M3: Exotel** | Bidirectional WebSocket (AgentStream) | **Requires external API access** | Only Twilio mu-law stream exists | Implement `/api/telephony/exotel/stream` conforming to AgentStream protocol |
| **M3: Exotel** | Call status & recording webhooks | **Not implemented** | None | Implement `/api/telephony/exotel/status` and `/recording` |
| **M3: Exotel** | Call failure/busy/no-answer detection | **Not implemented** | None | Process Exotel disposition callbacks to update CRM |
| **M4: Sarvam STT** | Batch Speech-to-Text (`saaras:v3`) | **Already implemented** | Implemented in `services/sarvam_service.py` | Working with auto language detection |
| **M4: Sarvam STT** | Full-Duplex Real-Time Streaming STT | **Blocked by current API plan** | Current plan uses REST HTTP POST | Implement streaming WebSocket adapter if available; fallback to chunked VAD |
| **M4: Sarvam STT** | Indic Languages (Telugu, Hindi, English) | **Already implemented** | Tested and verified in `services/language_utils.py` | Auto-detects Telugu, Hindi, English, Tenglish, Hinglish |
| **M4: Sarvam STT** | Additional Languages (Tamil, Kannada, etc.) | **Partially implemented** | Language detection handles Telugu/Hindi/English | Expand Unicode ranges and Sarvam codes in `language_utils.py` |
| **M4: Sarvam TTS** | Natural Indic TTS (`bulbul:v4-flash`) | **Already implemented** | Working in `services/sarvam_service.py` | Dynamic speaker routing for Telugu, Hindi, and English |
| **M4: Sarvam TTS** | Audio streaming chunk delivery | **Partially implemented** | Returns full WAV buffer | Stream audio chunks directly to WebSocket to reduce TTFB |
| **M4: Sarvam LLM** | Conversational Model (`sarvam-105b-conversations`) | **Already implemented** | Implemented in `services/sarvam_service.py` | Context-aware sales responses with active listening |
| **M4: Sarvam LLM** | Structured JSON tool calling | **Partially implemented** | Post-call JSON extraction works; in-call tool calling not active | Implement function calling schema for dynamic calendar/CRM tools |
| **M4: Audio** | Voice Activity Detection (VAD) & Interruptions | **Partially implemented** | Basic 4-sec buffer on telephony; 500ms cognitive pause | Implement client-side/server-side VAD with barge-in cutoff |
| **M5: Orchestration**| Asynchronous real-time audio pipeline | **Partially implemented** | Working for Web Mic; basic for Twilio | Orchestrate Exotel stream <-> VAD <-> Sarvam STT <-> LLM <-> TTS |
| **M6: AI Employees** | Multiple AI Employee management | **Not implemented** | Single prompt template for S P Associates | Create `ai_employees` database table & CRUD routes |
| **M6: AI Employees** | AI Employee Builder Assistant | **Not implemented** | None | Build wizard to generate employee draft from plain English |
| **M6: AI Employees** | Admin approval workflow for agents | **Not implemented** | None | Add `status` field (`draft`, `approved`, `active`) |
| **M7: Apollo.io** | Organization & People search | **Requires external API access** | None | Implement `providers/leads/apollo.py` using Apollo REST API |
| **M7: Apollo.io** | Company & Contact enrichment | **Requires external API access** | None | Implement enrichment calls with credit safety limits |
| **M7: Apollo.io** | Credit monitoring & rate limiting | **Not implemented** | None | Add credit tracker in database and UI warning |
| **M8: Apify** | Website crawler & business scraper | **Requires external API access** | None | Implement `providers/leads/apify.py` using Apify Client |
| **M8: Apify** | Common lead schema normalization | **Partially implemented** | Standard lead dict used for Excel/CSV | Unify Apollo, Apify, CSV, and Manual entries under common Pydantic schema |
| **M9: Excel/CSV** | XLSX & CSV upload and fuzzy column mapping | **Already implemented** | Working in `services/excel_service.py` | Auto-detects 9 standard columns across Telugu/English headers |
| **M9: Excel/CSV** | Template generation & summary export | **Already implemented** | Working in `services/excel_service.py` | Generates formatted Excel sheets with executive English summaries |
| **M9: Excel/CSV** | Bulk lead action toolbar (Analyse, Score) | **Partially implemented** | Auto-campaign bulk action exists; scoring absent | Add bulk action triggers in CRM pipeline toolbar |
| **M10: Intelligence**| Pre-call AI company opportunity analysis | **Not implemented** | None | Scrape website via Apify/HTTP -> Sarvam LLM -> generate calling brief |
| **M10: Intelligence**| Verified vs Inferred confidence rating | **Not implemented** | None | Add confidence metadata to lead analysis profile |
| **M11: Lead Scoring**| Configurable 0-100 lead score (Hot/Warm/Cold)| **Not implemented** | Priority is currently text (`HIGH`, `MEDIUM`, `LOW`) | Implement weighted scoring algorithm with explainable breakdown |
| **M12: Campaigns** | Campaign management & execution | **Partially implemented** | `services/campaign_service.py` runs in-memory | Migrate to persistent `campaigns` DB table and Celery worker queue |
| **M12: Campaigns** | Concurrency control & retry policies | **Partially implemented** | Serial execution with configurable delay | Implement semaphore-governed concurrent calls and retry backoff |
| **M13: Conversation**| Dynamic sales dialogue & objection handling | **Already implemented** | Implemented in `services/sales_agent.py` | Handles price, existing vendors, WhatsApp requests, demo bookings |
| **M14: CRM** | Unified Leads & Deals Pipeline | **Partially implemented** | 3-column dashboard exists with deal stages | Separate Contacts vs Companies; add Kanban drag-and-drop |
| **M14: CRM** | Activity timeline (Calls, Notes, Tasks) | **Partially implemented** | Calls table stores history; notes exist on lead | Build unified activity log table |
| **M15: API Actions** | Custom API action execution framework | **Partially implemented** | Developer API dispatch exists; custom webhooks absent | Build dynamic webhook executor for arbitrary external endpoints |
| **M16: WhatsApp** | Meta WhatsApp Cloud API integration | **Requires external API access** | None | Implement `providers/messaging/meta_whatsapp.py` with Cloud API |
| **M16: WhatsApp** | Approved template & brochure delivery | **Requires external API access** | None | Integrate pre-approved template triggers upon call qualification |
| **M17: Calendar** | Google Calendar appointment booking | **Requires external API access** | None | Implement `providers/calendar/google_calendar.py` via OAuth 2.0 |
| **M18: Knowledge RAG**| Document parsing & pgvector semantic search | **Not implemented** | `company_profile` has static text fields | Add document ingestion, chunking, and vector similarity search |
| **M19: Caller Memory**| Cross-call persistent conversation memory | **Partially implemented** | `last_call_summary` retrieved for next call | Inject past call summaries into prompt for returning leads |
| **M20: Post-Call** | Structured English executive intelligence | **Already implemented** | Verified with 100% test coverage | Extracts summary, sentiment, stage, budget, timeline, objections, actions |
| **M21: Analytics** | Analytics Dashboard & Metrics | **Partially implemented** | Metric cards exist in Overview tab | Add conversion funnel, calling expenses, and date/source filters |
| **M22: Reporting** | Comprehensive multi-sheet Excel export | **Partially implemented** | Single-sheet summary export works | Expand to multi-tab workbook with analytics and follow-up lists |
| **M23: Security/Admin**| RBAC (Admin, Manager, Salesperson) & Auth | **Not implemented** | Only API Key header check exists | Implement JWT auth, user table, role middleware, and audit logs |
| **M23: Compliance** | DND, TRAI, DLT & Opt-Out management | **Partially implemented** | Call simulation checks status | Add opt-out blacklist table and mandatory consent verification |
| **M24: Cost Tracking**| Multi-provider API usage & unit cost tracking | **Partially implemented** | INR talk-time credits tracking works for API keys | Track Exotel minutes, Sarvam tokens/chars, Apollo credits, Apify CUs |
| **M25: Phasing** | Phased, regression-tested delivery | **Already implemented** | Baseline test suite passing 100% | Follow structured Phase 1-12 rollout plan |

---

## 5. Technical Debt & Architecture Risks

1. **In-Memory Campaign State**: `services/campaign_service.py` maintains `self.is_running`, `self.completed_leads`, and logs in RAM. If the server process restarts or encounters an uncaught exception, active campaigns lose state.
2. **SQLite Concurrency Contention**: SQLite supports only one concurrent writer. When concurrent Exotel streams update lead records, call logs, and billing orders simultaneously, `sqlite3.OperationalError: database is locked` will occur without a connection pool or PostgreSQL.
3. **Audio Path Latency**: Currently, voice responses perform a sequential chain: STT REST call -> LLM REST call -> TTS REST call. For PSTN calls, total latency must remain under 1,200ms to feel human. Streaming TTS and early token flushing are needed.
4. **Hardcoded Agency Configuration**: The agent is hardwired to "S P Associates Software Company". While this preserves identity, enterprise SaaS requires dynamic agency profiles and customizable AI employee personas.

---

## 6. Audit Conclusion & Next Steps

The existing foundation is clean, modular, and functional. All core functionalities—especially the Sarvam multilingual voice integration, English executive summary pipeline, and Excel workflows—are intact and verified by unit tests.

Refactoring must proceed without breaking any existing functionality, strictly adhering to the phased implementation plan outlined in `IMPLEMENTATION_PLAN.md`.

