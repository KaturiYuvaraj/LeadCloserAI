# MASTER IMPLEMENTATION PLAN
**AI Sales Automation Platform (Outpero-Inspired)**
*Phased Architectural Roadmap & Execution Strategy*
*Document Version: 1.0.0 | Date: November 2, 2026*

---

## 1. Architectural Vision & Guiding Principles

The objective is to elevate the existing `telugu-ai-caller` into an enterprise-grade AI Sales Automation Platform inspired by Outpero, while maintaining independent integration of third-party APIs (Exotel, Sarvam AI, Apollo.io, Apify, Meta WhatsApp Cloud API, Google Calendar API, PostgreSQL, and Redis/Celery).

### Non-Negotiable Guiding Principles:
1. **Never Break Working Code**: All existing working features (Sarvam AI Telugu/Hindi/English calling, English executive call summaries, Excel import/export, Aurora porcelain light UI) must remain 100% operational at every phase.
2. **Provider-Agnostic Abstraction**: The core application logic must never directly couple to any single vendor SDK. Every external service must implement a documented abstract base interface.
3. **Graceful Fallback & Degradation**: If an external provider API is unconfigured, rate-limited, or unavailable, the application must automatically degrade gracefully (e.g., fallback from PSTN telephony to interactive browser web-calling; fallback from Apollo enrichment to manual/Excel data).
4. **Strict Data & Compliance Integrity**: All call summaries, CRM notes, and deal attributes must remain strictly recorded in professional executive English, respecting TRAI DLT, Indian data protection, and WhatsApp opt-in regulations.
5. **Phase-by-Phase Verification**: No phase shall commence until the preceding phase has passed its automated test suite and regression checks.

---

## 2. Target Architecture Overview

```
                                  +------------------------------------------+
                                  |         Outpero-Inspired Frontend        |
                                  |   (Aurora Light UI, CRM, Analytics, Admin)|
                                  +--------------------+---------------------+
                                                       |
                                            REST / WebSockets (FastAPI)
                                                       |
               +---------------------------------------+---------------------------------------+
               |                                       |                                       |
+--------------v---------------+       +---------------v--------------+       +----------------v--------------+
|     API Routers Layer        |       |    Orchestration Engine      |       |      Background Workers       |
| /api/leads, /api/campaigns   |       |   State, Pacing, VAD, Barge  |       |   Celery + Redis Task Queue   |
| /api/discovery, /api/telephony|      +---------------+--------------+       |  (Calling, Scraping, Sync)    |
+--------------+---------------+                       |                      +----------------+--------------+
               |                                       |                                       |
               +-----------------------+---------------+---------------------------------------+
                                       |
                        +--------------v--------------+
                        |  Modular Provider Interface |
                        +--------------+--------------+
                                       |
    +------------------+---------------+---------------+------------------+------------------+
    |                  |               |               |                  |                  |
+---v----+         +---v----+      +---v----+      +---v----+         +---v----+         +---v----+
| Voice  |         | Phone  |      |  LLM   |      | Leads  |         | Messages|        |Calendar|
| Sarvam |         | Exotel |      | Sarvam |      | Apollo |         | WhatsApp|        | Google |
|STT/TTS |         | PSTN/WS|      |  105B  |      | Apify  |         | CloudAPI|        |  v3    |
+--------+         +--------+      +--------+      +--------+         +---------+        +--------+
```

---

## 3. Detailed Phase-by-Phase Roadmap

### PHASE 1: Audit & Baseline Verification (Completed)
- **Scope**: Perform comprehensive code audit, inventory all files, inspect database schemas, verify all existing unit tests, and document technical debt.
- **Deliverables**:
  - `PROJECT_AUDIT.md` (completed)
  - `IMPLEMENTATION_PLAN.md` (this document)
  - `API_REQUIREMENTS.md` (third-party API specifications)
- **Verification Gate**:
  - Run all existing tests (`test_api.py`, `test_developer_api.py`, `test_english_summaries.py`, `test_campaign_and_excel.py`). All 8 test suites pass with 100%.

---

### PHASE 2: Modular Provider Architecture & Lead Schema Standardization
- **Scope**: Create an extensible provider interface layer under `telugu-ai-caller/providers/`.
- **Key Modules to Build**:
  - `providers/base.py`: Abstract base classes for all provider types (`VoiceProvider`, `TelephonyProvider`, `LLMProvider`, `LeadDiscoveryProvider`, `MessagingProvider`, `CalendarProvider`).
  - `providers/voice/`:
    - `base.py`: Defines `transcribe(audio_bytes, lang)`, `synthesize(text, lang, speaker)`.
    - `sarvam_stt.py`: Encapsulates Sarvam STT.
    - `sarvam_tts.py`: Encapsulates Sarvam TTS.
  - `providers/llm/`:
    - `base.py`: Defines `complete(messages, tools, temperature)`, `extract_intelligence(transcript)`.
    - `sarvam_llm.py`: Encapsulates Sarvam 105B Token Factory.
  - `providers/telephony/`:
    - `base.py`: Defines `initiate_call(to_phone, lead_id)`, `handle_stream(websocket)`.
    - `exotel.py`: Prepares Exotel adapter contract.
    - `twilio_legacy.py`: Wraps current working Twilio adapter for backward compatibility.
  - `schemas/lead.py`: Common normalized Pydantic lead schema used uniformly across Apollo, Apify, CSV, Excel, and manual entry.
  - Integration Settings View in UI with live connection test buttons for each provider.
- **Verification Gate**:
  - Unit tests verifying provider base class compliance.
  - Existing web call and telephony WebSocket continue functioning without disruption.

---

### PHASE 3: Apollo.io & Apify Lead Discovery Integration
- **Scope**: Build automated B2B lead discovery and website extraction modules.
- **Key Modules to Build**:
  - `providers/leads/apollo.py`:
    - Implements `search_organizations(industry, location, size)`.
    - Implements `search_people(job_titles, company_ids)`.
    - Implements `enrich_contact(email, phone, domain)` with strict credit safety thresholds.
    - Credit tracking and API usage safeguards to avoid unnecessary spend.
  - `providers/leads/apify.py`:
    - Configurable scraper adapter calling Apify Actors (`apify/web-scraper` or Google Maps scraper).
    - Website crawler extracting business description, services, digital presence, and public contacts.
    - Normalization into common `Lead` schema.
    - Robots.txt and domain access compliance.
  - UI Discovery Hub:
    - Search modal allowing users to discover leads by industry (e.g., Healthcare, Logistics, Retail in Hyderabad/Bangalore).
    - Bulk import discovered prospects directly into the CRM pipeline with 1 click.
- **Verification Gate**:
  - Mock and live credential integration tests (`tests/test_apollo_integration.py`, `tests/test_apify_integration.py`).
  - Deduplication test verifying that re-discovered leads update existing records without creating duplicates.

---

### PHASE 4: Exotel Telephony Integration (AgentStream)
- **Scope**: Integrate Exotel as the primary Indian telephony provider for outbound PSTN calling.
- **Key Modules to Build**:
  - `providers/telephony/exotel.py`:
    - Exotel Connect Voice AI API integration (`POST /v1/Accounts/{AccountSid}/Calls/connect.json`).
    - Configurable parameters: `EXOTEL_ACCOUNT_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_SUB_DOMAIN`, `EXOTEL_CALLER_ID`.
  - Secure WebSocket Endpoint:
    - `/api/telephony/exotel/stream`: Conforms to Exotel AgentStream message protocol (`connected`, `start`, `media`, `dtmf`, `stop`).
    - Audio transcoding: Support Exotel's native PCM 16-bit 8kHz/16kHz and G.711 mu-law audio streams.
    - Audio buffering & latency instrumentation (tracking time-to-first-byte and audio chunk delivery).
  - Callback Webhooks:
    - `/api/telephony/exotel/status`: Captures call dispositions (`completed`, `busy`, `no-answer`, `failed`, `canceled`).
    - `/api/telephony/exotel/recording`: Stores authenticated call recording URL in CRM record.
- **Verification Gate**:
  - WebSocket protocol unit tests with simulated Exotel AgentStream events.
  - Webhook callback validation tests.

---

### PHASE 5: Sarvam Real-Time Voice Pipeline Enhancement
- **Scope**: Enhance speech recognition and generation to minimize end-to-end conversation latency.
- **Key Modules to Build**:
  - Real-time Audio Processing:
    - Energy-based and streaming Voice Activity Detection (VAD) to detect when the customer has finished speaking.
    - Turn-taking latency optimization: Target response under 1,000ms.
    - Barge-in & Interruption Handling: If user audio is detected while the AI is speaking, immediately emit a stop/clear audio packet to the telephony WebSocket.
  - STT & TTS Pipeline:
    - Evaluate streaming STT capabilities on Sarvam AI.
    - Bulbul v4 Flash audio streaming: Chunk generated audio and stream directly to WebSocket to avoid waiting for the full WAV synthesis.
    - Trilingual support preserved for Telugu, Hindi, and Indian English with code-switching preservation.
- **Verification Gate**:
  - Interruption and barge-in unit tests (`tests/test_interruption_handling.py`).
  - Latency benchmark test measuring response turnaround times.

---

### PHASE 6: AI Employee Builder & Dynamic Conversation Engine
- **Scope**: Multi-agent creation and management allowing users to deploy specialized sales agents.
- **Key Modules to Build**:
  - Database Table `ai_employees`:
    - Columns: `id`, `name`, `role`, `language`, `voice_speaker`, `greeting`, `system_prompt`, `sales_script`, `qualification_criteria`, `status` (`draft`, `approved`, `active`), `working_hours`, `max_duration_seconds`.
  - Pre-Configured Specialized Agents:
    1. **Website & SaaS Development Specialist**: Pitching custom portals, redesigns, and SEO.
    2. **Mobile App Sales Closer**: Specializing in Flutter/React Native/iOS/Android quotes.
    3. **AI Voice & WhatsApp Automation Consultant**: Pitching AI telecalling and support chatbots.
    4. **ERP & Billing Software Consultant**: Tailored for retail and logistics automation.
  - AI Employee Creation Wizard:
    - Plain English prompt generator: User inputs "Create a Hindi sales closer for dental clinics" -> Generates structured prompt, script, and qualification rules.
    - Administrator approval gate before activation.
- **Verification Gate**:
  - Agent builder API tests (`tests/test_ai_employee_builder.py`).
  - Multi-agent isolation test ensuring different campaigns use distinct employee personas and voices.

---

### PHASE 7: Robust Campaign Management & Background Queues
- **Scope**: Replace in-memory campaign execution with persistent database records and Redis + Celery distributed workers.
- **Key Modules to Build**:
  - Database Table `campaigns`:
    - Columns: `id`, `name`, `description`, `employee_id`, `lead_ids`, `status` (`draft`, `scheduled`, `running`, `paused`, `completed`), `calling_hours_start`, `calling_hours_end`, `max_concurrency`, `retry_attempts`, `daily_limit`, `stats_json`.
  - Redis & Celery Integration:
    - Celery task `dispatch_campaign_call(campaign_id, lead_id)`.
    - Distributed concurrency locking via Redis semaphores (governing max parallel outbound calls).
    - Idempotency guards preventing double-calling the same lead within a single campaign window.
    - Automatic retry with exponential backoff on `busy` or `no-answer` dispositions.
- **Verification Gate**:
  - Campaign persistence test: Restarting application process preserves campaign progress without state loss.
  - Concurrency throttle verification test.

---

### PHASE 8: Enhanced CRM & Sales Pipeline Evolution
- **Scope**: Upgrade the 3-column CRM into a full-scale deal closing pipeline.
- **Key Modules to Build**:
  - Entity Separation:
    - `companies`: Firmographic data, domain, industry, size, tech stack, expansion signals.
    - `contacts`: Individual person records linked to companies (`name`, `phone`, `email`, `role`, `opt_out`).
    - `deals`: Value in INR, stage (`New Lead`, `Analyzed`, `Contacted`, `Interested`, `Qualified`, `Meeting Scheduled`, `Proposal Sent`, `Negotiation`, `Won`, `Lost`).
  - Interactive Pipeline View:
    - Kanban stage columns with visual cards and summary statistics.
    - Drag-and-drop deal stage progression.
  - Unified Activity Timeline:
    - Consolidates calls, audio playback, transcripts, WhatsApp messages, emails, and follow-up notes in a single chronologically sorted feed.
- **Verification Gate**:
  - Data migration test: Existing `leads` table cleanly migrates into `contacts` and `deals` without losing historical call logs.

---

### PHASE 9: Meta WhatsApp Cloud API & Google Calendar Integrations
- **Scope**: Close the loop after qualified calls by delivering instant brochures and booking meetings.
- **Key Modules to Build**:
  - Meta WhatsApp Cloud API (`providers/messaging/meta_whatsapp.py`):
    - Direct integration with Meta Graph API (`v19.0+`).
    - Automated delivery of approved message templates (e.g. `lead_followup_intro`, `meeting_confirmation`, `service_catalog_pdf`).
    - Inbound message webhook (`/api/webhooks/whatsapp`) to capture customer replies into the CRM activity feed.
    - Opt-in enforcement: Only send messages to verified prospects who consented during call or web capture.
  - Google Calendar API (`providers/calendar/google_calendar.py`):
    - OAuth 2.0 Web Client integration.
    - Real-time availability check via Google `freebusy` API.
    - Automatic meeting creation with Google Meet video link when the AI sales caller agrees with customer on a scheduled demo (e.g. "Tomorrow at 11:00 AM").
    - Sync calendar event link into CRM deal card and send meeting confirmation to customer via WhatsApp.
- **Verification Gate**:
  - Webhook signature verification tests.
  - Calendar booking conflict resolution tests.

---

### PHASE 10: RAG Knowledge Base & Persistent Caller Memory
- **Scope**: Enable AI callers to answer specific company questions using uploaded documents and recall previous discussions.
- **Key Modules to Build**:
  - Document Ingestion Pipeline:
    - Support uploading PDFs, service catalogues, pricing sheets, and scraping company URLs.
    - Text chunking (500 tokens with 50-token overlap).
    - Vector embeddings stored in PostgreSQL with `pgvector` (or fallback local vector index if PostgreSQL is optional in development).
    - Dynamic context injection: If client asks a specific question ("What is your pricing for React Native apps?"), query RAG and inject relevant context into the system prompt.
  - Persistent Caller Memory:
    - Look up customer phone number across all previous calls.
    - Extract past objections, agreed budgets, and promised follow-ups.
    - Inject memory into prompt: "Customer previously noted budget constraint of ₹50,000 on Oct 25; continue from previous negotiation."
- **Verification Gate**:
  - RAG precision retrieval test.
  - Multi-session memory recall test.

---

### PHASE 11: Post-Call Analytics & Comprehensive Multi-Tab Excel Reporting
- **Scope**: Deep-dive analytics, cost tracking, and downloadable Excel reporting.
- **Key Modules to Build**:
  - Advanced Analytics Dashboard:
    - Funnel metrics: Calls Attempted -> Connected -> Engaged -> Qualified -> Demos Booked -> Closed Won.
    - Answer rate, average call duration, cost per qualified lead (CPQL).
    - Campaign comparison charts and salesperson performance tracking.
  - Multi-Tab OpenPyXL Excel Export:
    - Sheet 1: `Executive Summary & Pipeline Metrics`
    - Sheet 2: `Enriched Leads & Company Intelligence`
    - Sheet 3: `Complete Call Logs & English Summaries`
    - Sheet 4: `Actionable Follow-Up Queue`
- **Verification Gate**:
  - Multi-tab Excel generation and schema validation tests.

---

### PHASE 12: Administration, Security Hardening & Final Acceptance Testing
- **Scope**: Security, RBAC, TRAI/DLT compliance, and the complete 26-step Final Acceptance Test.
- **Key Modules to Build**:
  - RBAC & Authentication:
    - JWT authentication with secure password hashing (`bcrypt`).
    - Roles: `SuperAdmin`, `SalesManager`, `SalesCloser`.
    - Organization-level data isolation.
  - Compliance Engine:
    - DND (Do Not Call) registry blacklist check before initiating any outbound call.
    - Opt-out detection: If customer says "Don't call me again", automatically flag `opt_out=TRUE` and prevent future dialer queues.
  - Comprehensive Cost & Usage Tracking:
    - Track unit consumption: Exotel call minutes, Sarvam STT/TTS characters, LLM tokens, Apollo credits, Apify CUs, and WhatsApp charges.
- **Final Acceptance Verification**:
  - Execute the end-to-end 26-step real-world workflow from Excel upload to Exotel PSTN call, Sarvam multilingual dialogue, objection handling, English summary generation, WhatsApp brochure, Google Calendar invite, and Excel report export.

---

## 4. Phase Execution Summary & Rollout Gates

| Phase | Milestone Name | Key Dependencies | Primary Deliverable | Regression Risk |
|---|---|---|---|---|
| **Phase 1** | Audit & Gap Analysis | None | `PROJECT_AUDIT.md`, `IMPLEMENTATION_PLAN.md` | None (Read-only) |
| **Phase 2** | Provider Interface Layer | FastAPI, Pydantic | Abstract base classes under `providers/` | Low (Wraps existing services) |
| **Phase 3** | Apollo & Apify Discovery | Apollo API, Apify Client | `providers/leads/` + Lead Discovery UI | Low (New feature) |
| **Phase 4** | Exotel Telephony Integration | Exotel AgentStream | `providers/telephony/exotel.py` + WebSockets | Medium (Telephony audio streaming) |
| **Phase 5** | Sarvam Real-Time Voice | Sarvam AI, VAD | Streaming TTS chunks + Barge-in handling | Medium (Voice latency) |
| **Phase 6** | AI Employee Builder | Sarvam LLM, SQLite | Multi-agent builder + prompt generator | Low (Extends prompt engine) |
| **Phase 7** | Persistent Campaigns & Celery | Redis, Celery | Distributed calling queue & retry engine | Medium (Background tasks) |
| **Phase 8** | CRM & Sales Pipeline | SQLite / PostgreSQL | Kanban pipeline + Activity feed | Low (Expands CRM views) |
| **Phase 9** | WhatsApp & Google Calendar | Meta Cloud API, Google v3 | Automated follow-up messages & demo booking | Low (External webhooks) |
| **Phase 10**| RAG Knowledge Base & Memory | pgvector / Embeddings | Document ingestion + customer recall | Medium (Retrieval accuracy) |
| **Phase 11**| Analytics & Multi-Tab Excel | OpenPyXL, Pandas | Multi-tab executive Excel reports | Low (Reporting layer) |
| **Phase 12**| Security, RBAC & Acceptance | JWT, DND engine | Full 26-step verification & hardening | Low (Hardening & audit) |

---

## 5. Rollback & Database Migration Strategy

1. **Database Schema Evolution**:
   - Every schema change will use additive column checks (`PRAGMA table_info`) or versioned migration scripts so older SQLite databases upgrade automatically without data loss.
   - For PostgreSQL migration in later phases, an automated SQLite-to-Postgres data exporter script will be provided.
2. **Feature Flags**:
   - Each new integration (Exotel, Apollo, Apify, WhatsApp, Google Calendar) will be governed by environment flags and provider configuration toggles in the database.
   - If an API key is absent, the UI cleanly notifies the administrator and falls back to existing manual/browser simulation modes without raising 500 errors.
3. **Automated Regression Testing**:
   - The test suite (`pytest` / `unittest`) will run automatically after each phase. If any pre-existing test fails, work will halt until the regression is resolved.

