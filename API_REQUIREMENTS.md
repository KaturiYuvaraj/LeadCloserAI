# API REQUIREMENTS & THIRD-PARTY PROVIDER SPECIFICATION
**AI Sales Automation Platform (Outpero-Inspired)**
*Technical Specification & Integration Reference*
*Document Version: 1.0.0 | Date: November 2, 2026*

---

## 1. Provider Technology Evaluation & Specification

The platform architecture integrates 10 chosen technology providers to power all sales automation, lead discovery, speech, telephony, scheduling, and data workflows.

```
+-----------------------------------------------------------------------------------------------+
|                               TECHNOLOGY PROVIDERS EVALUATION                                 |
+----+-----------------------+-----------------------------+------------------------------------+
| #  | Provider Name         | Capability Domain           | Primary Integration Protocol       |
+----+-----------------------+-----------------------------+------------------------------------+
| 1  | Exotel                | PSTN Telephony & Streaming  | REST API + AgentStream (WebSocket) |
| 2  | Sarvam AI             | Indic Multilingual Voice    | REST API + Streaming WebSocket     |
| 3  | Apollo.io             | B2B Contact & Co Discovery  | REST API v2                        |
| 4  | Apify                 | Web Crawling & Scraping     | REST API & Actor Client            |
| 5  | Meta WhatsApp Cloud   | Direct Business Messaging   | Meta Graph API v19.0+ & Webhooks   |
| 6  | Google Calendar API   | Appointment Scheduling      | Google REST API v3 (OAuth 2.0)     |
| 7  | PostgreSQL            | Relational & Vector Storage | asyncpg / psycopg2 + pgvector      |
| 8  | Redis + Celery        | Distributed Background Task | Redis Broker + Celery Worker       |
| 9  | FastAPI               | Asynchronous ASGI Backend   | Python 3.9+ ASGI Framework         |
| 10 | n8n (Optional)        | External Workflow Engine    | Webhook Triggers                   |
+----+-----------------------+-----------------------------+------------------------------------+
```

---

## 2. Deep-Dive Provider Specifications

### 2.1. Exotel Telephony & Bidirectional Voice Streaming
- **Official Documentation**: https://developer.exotel.com/
- **Role**: Primary Indian PSTN outbound dialing, telephone carrier connection, and live audio streaming.
- **Key Products**: Exotel Connect Voice AI & Exotel AgentStream.
- **API Base URLs**:
  - Mumbai (Standard): `https://api.exotel.com/v1/Accounts/{AccountSid}/`
  - Singapore: `https://api.in.exotel.com/v1/Accounts/{AccountSid}/`
- **Authentication**: HTTP Basic Auth (`EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`).
- **Required Credentials**:
  - `EXOTEL_ACCOUNT_SID`: Account identifier.
  - `EXOTEL_API_KEY`: API authentication key.
  - `EXOTEL_API_TOKEN`: API secret token.
  - `EXOTEL_SUB_DOMAIN`: Cluster subdomain (e.g., `api.exotel.com` or `api.in.exotel.com`).
  - `EXOTEL_CALLER_ID`: Registered ExoPhone virtual number for outbound CLI presentation.
- **Endpoints to Implement**:
  - `POST /v1/Accounts/{AccountSid}/Calls/connect.json`:
    - Initiates outbound PSTN call connecting customer to the AgentStream WebSocket.
    - Payload parameters: `From` (customer phone), `CallerId` (ExoPhone), `Url` (Callback / Flow URL), `StreamUrl` (`wss://your-domain.com/api/telephony/exotel/stream`).
  - `WebSocket /api/telephony/exotel/stream`:
    - Bi-directional audio stream between Exotel media gateway and Python backend.
    - **Audio Codec**: G.711 mu-law (8kHz, 8-bit) or Linear PCM (16-bit, 8kHz or 16kHz).
    - **Inbound Events**: `connected`, `start` (stream metadata, CallSid), `media` (base64 audio payload chunks), `dtmf` (keypresses), `stop` (call teardown).
    - **Outbound Events**: `media` (base64 audio response chunks), `clear` (barge-in interruption cutoff).
  - Webhooks:
    - `POST /api/telephony/exotel/status`: Captures call dispositions (`completed`, `busy`, `no-answer`, `failed`, `canceled`).
    - `POST /api/telephony/exotel/recording`: Captures recording URL upon call completion.

---

### 2.2. Sarvam AI Real-Time Voice & Multilingual LLM Engine
- **Official Documentation**: https://docs.sarvam.ai/
- **Role**: Indian multilingual speech recognition, voice synthesis, and conversational intelligence.
- **Authentication**: Header `api-subscription-key: {SARVAM_API_KEY}`.
- **Endpoints**:
  - **Speech-to-Text (STT)**:
    - Endpoint: `POST https://api.sarvam.ai/speech-to-text`
    - Model: `saaras:v3` (or `saaras:v4` where enabled on enterprise accounts).
    - Language Code: `unknown` (auto-detects Indic languages, code-switching, Tenglish, Hinglish) or explicit codes (`te-IN`, `hi-IN`, `en-IN`, `ta-IN`, `kn-IN`).
    - Audio Input: 16kHz 16-bit PCM WAV.
  - **Text-to-Speech (TTS)**:
    - Endpoint: `POST https://api.sarvam.ai/text-to-speech`
    - Model: `bulbul:v4-flash` (fastest turnaround) or `bulbul:v3`.
    - Constraints: Maximum 2,500 characters per request; temperature between 0.1 and 1.0.
    - Dynamic Speakers:
      - Telugu: `kavitha_te_conversation` (conversational female), `tarun_te_narration` (male).
      - Hindi: `aditya_hi_sales` / `aditya` (persuasive male).
      - Indian English: `simran_en_sales` / `simran` (clear professional female).
  - **LLM Chat Completions**:
    - Endpoint: `POST https://api.sarvam.ai/v1/chat/completions`
    - Model: `sarvam-105b-conversations`.
    - Parameters: `temperature=0.5` for dynamic sales dialogue, `temperature=0.1-0.2` for post-call structured JSON extraction.

---

### 2.3. Apollo.io Lead Discovery & Enrichment
- **Official Documentation**: https://docs.apollo.io/
- **Role**: B2B prospect search, firmographic intelligence, job title filtering, and verified contact data.
- **Authentication**: Header `X-Api-Key: {APOLLO_API_KEY}`.
- **Base URL**: `https://api.apollo.io/v1/`
- **Key Endpoints**:
  - `POST /v1/mixed_people/search`:
    - Searches individual decision-makers.
    - Filters: `person_titles[]` (e.g. `CEO`, `Founder`, `CTO`, `Managing Director`, `Owner`), `organization_locations[]` (e.g. `Hyderabad`, `Telangana`, `India`), `organization_num_employees_ranges[]` (e.g. `1,10`, `11,50`).
    - Rate Limits & Pagination: Page size max 100, page index.
  - `POST /v1/organizations/enrich`:
    - Enriches company domain with industry, employee count, estimated revenue, technologies used, and LinkedIn URL.
  - `POST /v1/people/match`:
    - Enriches a single contact's phone and verified corporate email.
- **Credit Safeguards**:
  - Track credit usage before calling enrichment endpoints.
  - Allow admin to set a maximum daily credit consumption limit.

---

### 2.4. Apify Web Crawling & Public Business Scraping
- **Official Documentation**: https://docs.apify.com/
- **Role**: Deep website crawling, public directory search, service extraction, and expansion signals.
- **Authentication**: Header `Authorization: Bearer {APIFY_API_TOKEN}`.
- **Base URL**: `https://api.apify.com/v2/`
- **Key Actors**:
  - `apify/web-scraper` / `apify/cheerio-scraper`: Crawls prospect homepages, `/about-us`, `/services`, `/contact` to extract core offerings and contact emails.
  - `compass/crawler-google-places`: Permitted public discovery of local businesses (clinics, retail stores, transport firms) in target regions.
- **Execution Flow**:
  1. Trigger Actor run via `POST /v2/acts/{actorId}/runs`.
  2. Monitor run status asynchronously or receive Apify Webhook.
  3. Retrieve dataset items via `GET /v2/datasets/{datasetId}/items`.
  4. Normalize raw JSON into standard `Lead` schema.
- **Compliance Rules**:
  - Honor `robots.txt` directives.
  - Never bypass CAPTCHAs, paywalls, or authenticated user portals.

---

### 2.5. Meta WhatsApp Cloud API
- **Official Documentation**: https://developers.facebook.com/docs/whatsapp/cloud-api/
- **Role**: Immediate post-call delivery of brochures, pricing sheets, and meeting confirmations.
- **Authentication**: Bearer Token `WHATSAPP_ACCESS_TOKEN` (Meta System User Token).
- **Base URL**: `https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/`
- **Required Credentials**:
  - `WHATSAPP_PHONE_NUMBER_ID`: Registered WhatsApp Business phone number ID.
  - `WHATSAPP_BUSINESS_ACCOUNT_ID`: Meta Business Account ID.
  - `WHATSAPP_ACCESS_TOKEN`: Permanent System User access token with `whatsapp_business_messaging` permissions.
  - `WHATSAPP_WEBHOOK_VERIFY_TOKEN`: Custom verification secret for webhook handshake.
  - `WHATSAPP_APP_SECRET`: App secret for `X-Hub-Signature-256` payload validation.
- **Key Endpoints**:
  - `POST /v19.0/{PhoneId}/messages`:
    - Sends pre-approved template messages (e.g., `lead_intro_brochure`, `meeting_zoom_confirmation`).
    - Media attachments: Send downloadable PDF brochures stored in Cloud Storage or public static URL.
  - `GET /api/webhooks/whatsapp`: Webhook verification endpoint (responds with `hub.challenge`).
  - `POST /api/webhooks/whatsapp`: Webhook event listener for incoming messages, read receipts, and delivery reports.
- **Compliance Rules**:
  - Only message customers who consented during the voice call ("Can I send our brochure on WhatsApp? Yes").
  - Use Meta-approved templates for proactive business-initiated messages.

---

### 2.6. Google Calendar API
- **Official Documentation**: https://developers.google.com/calendar/api
- **Role**: Automated checking of sales team availability and booking confirmed live meetings.
- **Authentication**: OAuth 2.0 Web Client (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`).
- **Base URL**: `https://www.googleapis.com/calendar/v3/`
- **Key Endpoints**:
  - `POST /v3/freeBusy`:
    - Queries calendar availability for specified time window (e.g., tomorrow 10:00 AM to 5:00 PM).
    - Prevents double-booking.
  - `POST /v3/calendars/{calendarId}/events`:
    - Creates confirmed sales meeting event.
    - Features: Automatic Google Meet conference link generation (`conferenceDataVersion=1`), customer email invite, 15-minute reminder notification.
- **Timezone Management**: Strict Indian Standard Time (`Asia/Kolkata` / UTC+5:30) conversion.

---

### 2.7. PostgreSQL & pgvector (Database & Semantic RAG)
- **Role**: High-concurrency enterprise relational database and semantic vector storage for knowledge base RAG.
- **Configuration**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`.
- **Extensions**:
  - `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
  - `CREATE EXTENSION IF NOT EXISTS "pgvector";`
- **Connection Pool**: Asynchronous connection pool via `asyncpg` (min 5, max 25 connections).

---

### 2.8. Redis & Celery (Background Processing & Queuing)
- **Role**: Distributed task execution, rate limiting, and persistent auto-calling queue management.
- **Configuration**:
  - `REDIS_URL`: `redis://localhost:6379/0`
  - `CELERY_BROKER_URL`: `redis://localhost:6379/0`
  - `CELERY_RESULT_BACKEND`: `redis://localhost:6379/1`
- **Task Queues**:
  - `calling_queue`: High priority outbound call initiation tasks.
  - `scraping_queue`: Long-running Apify and website extraction tasks.
  - `messaging_queue`: WhatsApp message delivery and retries.
  - `analytics_queue`: Post-call intelligence extraction and reporting.

---

### 2.9. FastAPI Backend Framework
- **Role**: Primary ASGI web framework delivering REST APIs, WebSockets, static files, and Jinja2 templates.
- **Current Version**: `0.111.0` on Python 3.9+.
- **Middleware**: CORSMiddleware, GzipMiddleware, RateLimitMiddleware, RequestTimingMiddleware.

---

### 2.10. n8n Integration (Optional Workflow Automation)
- **Role**: External visual workflow triggers.
- **Implementation**: Outbound webhooks emitted on key milestones (`lead_qualified`, `call_completed`, `deal_won`) with HMAC SHA-256 signature headers.

---

## 3. Comprehensive Environment Variables Matrix (`.env.example`)

Below is the complete, production-ready environment configuration schema:

```ini
# =====================================================================
# 1. APPLICATION & SERVER SETTINGS
# =====================================================================
APP_ENV=development
APP_NAME=LeadCloserAI
SECRET_KEY=generate_a_random_32_byte_secret_key_here
HOST=0.0.0.0
PORT=8000
BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# =====================================================================
# 2. SARVAM AI CONFIGURATION (MANDATORY VOICE & LLM ENGINE)
# Get credentials at: https://sarvam.ai
# =====================================================================
SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_BASE_URL=https://api.sarvam.ai
DEFAULT_STT_MODEL=saaras:v3
DEFAULT_TTS_MODEL=bulbul:v4-flash
DEFAULT_TTS_SPEAKER=kavitha_te_conversation
DEFAULT_LLM_MODEL=sarvam-105b-conversations

# =====================================================================
# 3. EXOTEL TELEPHONY CONFIGURATION (INDIAN PSTN CALLING)
# Get credentials at: https://developer.exotel.com
# =====================================================================
EXOTEL_ACCOUNT_SID=
EXOTEL_API_KEY=
EXOTEL_API_TOKEN=
EXOTEL_SUB_DOMAIN=api.exotel.com
EXOTEL_CALLER_ID=
EXOTEL_STREAM_URL=wss://your-domain.com/api/telephony/exotel/stream

# =====================================================================
# 4. APOLLO.IO B2B LEAD DISCOVERY & ENRICHMENT
# Get credentials at: https://developer.apollo.io
# =====================================================================
APOLLO_API_KEY=
APOLLO_DAILY_CREDIT_LIMIT=50

# =====================================================================
# 5. APIFY WEB SCRAPING & BUSINESS CRAWLER
# Get credentials at: https://console.apify.com
# =====================================================================
APIFY_API_TOKEN=
APIFY_DEFAULT_ACTOR_ID=apify/web-scraper

# =====================================================================
# 6. META WHATSAPP CLOUD API (DIRECT MESSAGING)
# Get credentials at: https://developers.facebook.com
# =====================================================================
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_WEBHOOK_VERIFY_TOKEN=leadcloser_webhook_secret_token_123
WHATSAPP_APP_SECRET=

# =====================================================================
# 7. GOOGLE CALENDAR API (MEETING SCHEDULING)
# Get credentials at: https://console.cloud.google.com
# =====================================================================
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_CALENDAR_ID=primary

# =====================================================================
# 8. DATABASE CONFIGURATION (SQLITE DEV / POSTGRES PROD)
# =====================================================================
DATABASE_TYPE=sqlite
DATABASE_PATH=leads_crm.db
# PostgreSQL (Optional / Production):
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=leads_closer_db

# =====================================================================
# 9. REDIS & CELERY TASK QUEUE
# =====================================================================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# =====================================================================
# 10. OPTIONAL N8N WORKFLOW AUTOMATION
# =====================================================================
N8N_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=
```

---

## 4. Security & Credential Storage Architecture

1. **System Environment Variables**: Core infrastructure secrets (database credentials, Redis connection, master secret key) are strictly loaded via `.env` and never written to disk or exposed over API responses.
2. **User-Provided API Credentials**:
   - For credentials entered via the UI Settings Page (e.g. Apollo Key, Apify Token, WhatsApp Token), they must be encrypted at rest using AES-256 (via Python's `cryptography.fernet.Fernet` keyed to `SECRET_KEY`).
   - Stored in a secure `provider_settings` table:
     ```sql
     CREATE TABLE provider_settings (
         provider_name TEXT PRIMARY KEY,
         is_enabled BOOLEAN DEFAULT FALSE,
         encrypted_config TEXT NOT NULL,
         last_tested_at TIMESTAMP,
         last_status TEXT DEFAULT 'untested',
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     );
     ```
   - In API responses, sensitive secrets must be masked (e.g., `sk_live_****...abcd`).

---

## 5. Cost & Unit Usage Tracking Formulas

The platform maintains live cost calculation metrics across each calling campaign:

$$\text{Call Cost (INR)} = (\text{Duration Mins} \times \text{Exotel Rate}) + (\text{STT Seconds} \times \text{STT Rate}) + (\text{TTS Chars} \times \text{TTS Rate}) + (\text{LLM Tokens} \times \text{LLM Rate})$$

$$\text{Campaign Cost} = \sum \text{Call Cost} + (\text{Apollo Credits} \times \text{Credit Rate}) + (\text{Apify CUs} \times \text{CU Rate}) + (\text{WhatsApp Msgs} \times \text{Msg Rate})$$

$$\text{Cost Per Qualified Lead (CPQL)} = \frac{\text{Total Campaign Cost}}{\text{Number of Qualified Leads}}$$

All unit rates are configurable by the administrator in the UI and never hardcoded into business logic.

