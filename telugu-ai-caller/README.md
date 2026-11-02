# Telugu AI Caller & Lead Closer

A Telugu-first lead CRM and voice-sales workspace. The browser caller records
speech, transcribes it with Sarvam, generates a short Telugu or Tenglish reply,
and stores post-call intelligence in SQLite. Twilio Media Streams can be used
for phone calls when telephony credentials are configured.

## Start locally

1. Set `SARVAM_API_KEY` in `.env`. Add Twilio values only if you intend to use
   the phone-call integration.
2. Activate the virtual environment: `venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Start the API: `uvicorn main:app --reload`
5. Open `http://127.0.0.1:8000`.

The SQLite file defaults to `leads_crm.db` beside the code, regardless of the
folder from which the app is started. Set `DATABASE_PATH` to place it elsewhere.

## Main routes

- `GET /api/leads`, `POST /api/leads`, `PUT /api/leads/{id}`: manage CRM leads.
- `GET /api/calls`: review call history and extracted deal intelligence.
- `POST /api/tts/test`: preview the configured Sarvam Telugu voice.
- `POST /api/call/outbound`: passes a phone number to the configured telephony
  provider. Do not enable it without a documented consent and DND workflow.
- `POST /telephony/twiml`: TwiML endpoint for a Twilio Media Stream.

## Configuration

`BASE_URL` must be a public HTTPS address before using Twilio. `CORS_ORIGINS`
is a comma-separated list and defaults to local development URLs. The default
Sarvam configuration uses `sarvam-105b-conversations` and `bulbul:v4-flash`.

## Tests

Run offline checks with `python -m unittest discover -s tests`. The CRM API
tests create a temporary database and mock the telephony adapter; they do not
use the Sarvam key or place calls.

## Production checklist

- Use a managed database, migrations, backups, and encrypted secret storage.
- Verify Twilio webhook signatures and restrict `CORS_ORIGINS` to your UI.
- Record consent, respect DND/opt-out requests and local calling-time rules
  before enabling outbound calls.
