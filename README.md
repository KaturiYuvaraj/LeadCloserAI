# 🎙️ LeadCloserAI: Multilingual Autonomous AI Voice Caller & Lead Closing CRM

An autonomous, real-time AI Voice Calling & Deal Closing CRM built for Software, IT, and Agency Businesses representing **S P Associates Software Company**. 

It conducts fluent, human-like conversations in **Telugu**, **Hindi**, and **Indian English**, intelligently matches customer language in real time, handles price and timeline objections, schedules project demos, and automatically saves executive post-call intelligence and summaries in English.

Powered by **Sarvam AI** (`sarvam-105b-conversations`, `bulbul:v4-flash`, `saaras:v3`) and **FastAPI**.

---

## 🌟 Key Capabilities

### 1. 📊 Excel & CSV Sheet Lead Ingestion
- **Spreadsheet Upload:** Admin can upload `.xlsx`, `.xls`, or `.csv` files containing customer leads.
- **Smart Column Auto-Detection:** Automatically maps fields for Name, Phone Number, Company, Service Needed, Budget, Timeline, Preferred Language, and Notes.
- **Sample Template:** Download a pre-formatted Excel template (`leads_template.xlsx`) directly from the UI.
- **Duplicate Prevention:** Existing phone numbers are automatically detected and updated without creating duplicate entries.

### 2. ⚡ Autonomous Auto-Calling Campaigns
- **Batch Calling:** Click `▶️ Auto-Call Campaign` to dial through imported leads consecutively.
- **Personalized Context:** AI dynamically pulls each customer's details (name, company, service requested, budget, and prior call history) into the conversation prompt.
- **Live Real-Time Feedback:** Shows live progress, active call status, and live counters for Demos Booked, Closed Won, and Follow-ups.
- **Campaign Controls:** Instant Pause, Resume, and Stop controls from the dashboard.
- **Dual Calling Modes:**
  - *Autonomous AI Simulation:* High-speed automated dialogue execution for batch lead closing and test campaigns.
  - *Real Carrier Telephony (Twilio / WebSockets):* Dials real phone numbers with bidirectional audio streaming.

### 3. 🗣️ Multilingual Conversational Engine (Telugu • Hindi • English)
- **Automatic Language Matching:** Seamlessly detects and answers in the customer's preferred language (**Telugu**, **Hindi**, or **English**) or immediately switches when asked.
- **Natural Human Turn-Taking & Pacing:**
  - Web Audio API Voice Activity Detection (VAD) with an adaptive 1.8s silence endpoint detector.
  - Mic echo suppression during AI playback.
  - Empathetic acknowledgement openers before presenting solutions (*"సరేనండి, అర్థమైంది..."*, *"जी बिल्कुल सर, समझ गया..."*, *"Got it, absolutely..."*).
  - Short, focused responses (1-2 sentences) ending with a clear call-to-action.

### 4. 📝 Executive Post-Call Summaries in English
- Post-call sales intelligence extraction records **Call Summary**, **Deal Stage**, **Sentiment**, **Extracted Budget**, **Timeline**, **Objections**, and **Next Action Items**.
- **100% Professional English:** Summaries and CRM tasks are strictly translated and formatted into fluent English for executive review, regardless of call language.
- **Export to Excel:** Export all leads with updated call summaries and closing stages with one click.

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
    ├── database.py                 # SQLite CRM for Leads, Calls, Deals & Agency Profile
    ├── config.py                   # Configuration and environment loader
    ├── migrate_to_english_summaries.py # Database summary migration script
    ├── services/
    │   ├── sarvam_service.py       # Sarvam STT, TTS, and 105B LLM async client
    │   ├── sales_agent.py          # Sales dialogue engine, objection handler & extractor
    │   ├── campaign_service.py     # Background auto-calling campaign engine
    │   ├── excel_service.py        # Excel/CSV parser and summary exporter
    │   ├── language_utils.py       # Language detection and voice mapping
    │   ├── audio_processor.py      # Audio conversion (PCM, WAV, mu-law)
    │   └── telephony_service.py    # Twilio outbound calling and TwiML generator
    ├── static/
    │   ├── css/style.css           # Clean modern CRM dashboard styles
    │   └── js/
    │       ├── app.js              # CRM UI state, lead selection, and modals
    │       └── call_client.js      # Web Audio mic streaming and turn-taking VAD
    ├── templates/
    │   └── index.html              # Responsive CRM Dashboard & Calling Station
    └── tests/
        ├── test_developer_api.py   # Tests API key generation, billing & call dispatch
        ├── test_english_summaries.py # Verifies 100% English CRM summary storage
        ├── test_pacing_and_turn_taking.py # Verifies conversational timing & human pacing
        ├── test_campaign_and_excel.py # Tests Excel import/export & auto campaigns
        ├── test_multilingual.py    # Tests Telugu, Hindi, and English interactions
        ├── test_api.py             # Unit tests for CRM REST endpoints
        └── test_pipeline.py        # End-to-end integration test
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
Open `telugu-ai-caller/.env` and insert your Sarvam API key:
```env
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

Run tests to verify multilingual sales flow, turn-taking, and summary extraction:

```bash
# Developer API & Credit Billing test
python tests/test_developer_api.py

# English summaries & CRM database test
python tests/test_english_summaries.py

# Turn-taking pacing & VAD test
python tests/test_pacing_and_turn_taking.py

# Excel template & Auto-call campaign test
python tests/test_campaign_and_excel.py
```

---

## ⚡ Developer REST API Endpoints

Clients can purchase API credits and trigger calls programmatically:

### 1. Trigger Outbound AI Call
```bash
POST /api/v1/calls/dispatch
Header: Authorization: Bearer lc_live_...
Content-Type: application/json

{
  "lead_name": "Ramesh Naidu",
  "phone": "+919848011223",
  "company": "Naidu Supermarkets",
  "service": "Mobile App & Billing",
  "budget": "₹75,000",
  "language": "te-IN"
}
```

### 2. Purchase API Credits (₹ INR)
```bash
POST /api/v1/billing/purchase-credits
{
  "api_key_id": 1,
  "plan_name": "Business Growth",
  "amount_inr": 4999.0,
  "payment_method": "Instant UPI / Razorpay",
  "customer_email": "developer@client.com"
}
```

---

## 🛡️ License

Developed for **S P Associates Software Company**. All rights reserved.
