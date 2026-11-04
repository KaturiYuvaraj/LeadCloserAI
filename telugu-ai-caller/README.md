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

## Real-time voice engine (Pipecat)

The dashboard's **Start AI Call** uses a real-time engine built on Pipecat with
Sarvam streaming speech-to-text, `sarvam-105b-conversations` and `bulbul:v4-flash`
streaming text-to-speech. The browser talks to it over WebRTC. Callers can
interrupt the AI, and the voice switches automatically between Telugu, Hindi
and English. Typical reply time is about 2 seconds or less.

**Python 3.13 is required for this engine** (Pipecat does not support 3.14 yet):

```powershell
py -3.13 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Python 3.14 the app still installs and runs. The dashboard then falls back
to the classic engine (`/ws/web-call`). You can also force the classic engine
with `VOICE_ENGINE=classic` in `.env`.

Without a local PostgreSQL server, set `DATABASE_URL=sqlite:///./leads_dev.db`
in `.env` for development.

Routes: `POST /api/voice/offer` (start a call), `POST /api/voice/sessions/{id}/hangup`,
`GET /api/voice/sessions/{id}/summary`, `GET /api/voice/config.js`. The engine lives in
`voice_agent/` (`session.py` builds the pipeline, `language.py` routes languages).

### Phone calls (Exotel)

The same engine answers phone calls through Exotel's **Voicebot** applet, at
`wss://<your-host>/api/voice/exotel/stream`.

1. Expose the app over HTTPS. For development, use `cloudflared tunnel --url http://localhost:8000`.
2. In Exotel, go to **App Bazaar** and create the flow **Call Start → Voicebot → Hangup**.
   Set the Voicebot URL to `wss://<tunnel-host>/api/voice/exotel/stream`.
3. In **ExoPhones**, set your number's **Installed App** to that flow.

Outbound calls pass the lead as a custom parameter (`lead_id`), or append
`?lead_id=<id>&lang=te-IN` to the stream URL. For inbound calls, the caller's
number is matched to an existing lead (last 10 digits). Calls are saved with
`call_type = phone` and the Exotel call SID.

**Test without an Exotel account** using the fake Exotel caller. It streams a
WAV file as 8 kHz phone audio, records the bot, and measures the reply gap:

```powershell
python tests/fake_exotel/client.py --wav tests/fake_exotel/samples/three_questions.wav --lead-id 1
python tests/fake_exotel/client.py --wav tests/fake_exotel/samples/three_questions.wav --parallel 3   # load test
```

Add `--url ws://127.0.0.1:<port>/api/voice/exotel/stream` if the app isn't on port 8000.
These runs use real Sarvam calls, so they cost a few rupees each.

### Phone calls (Vobiz, including numbers rented from Sarvam)

Sarvam's "Rent from Sarvam" numbers are Vobiz numbers. With a Vobiz number connected to
your own application, calls run on this engine with 16 kHz Linear16 audio:

1. Expose the app over HTTPS (as above).
2. In Vobiz, create an **application**:
   - **Answer URL:** `https://<tunnel-host>/api/voice/vobiz/answer` (POST)
   - **Hangup URL:** `https://<tunnel-host>/api/voice/vobiz/hangup` (POST)
3. Attach your number to that application.

The Answer URL returns `<Stream>` XML pointing at `wss://<host>/api/voice/vobiz/stream`
(the same host the request came in on; set `VOICE_PUBLIC_WS_BASE=wss://your-host` to
override). Add `?lead_id=<id>&lang=te-IN` to the Answer URL for outbound calls to a lead.

Test it without an account. The fake caller fetches the Answer URL like Vobiz does:

```powershell
python tests/fake_exotel/client.py --provider vobiz --wav tests/fake_exotel/samples/three_questions.wav --lead-id 1
```

Use `--answer-url http://127.0.0.1:<port>/api/voice/vobiz/answer` if the app isn't on port 8000.

### Real-call handling

The engine handles real phone conditions (`voice_agent/call_guard.py`, `actions.py`, `knowledge.py`):

| Situation | What happens |
|---|---|
| Background noise | RNNoise cleans phone audio before speech recognition (`VOICE_NOISE_FILTER=off` disables it) |
| Long pauses mid-sentence | Smart end-of-turn model waits up to 3 s if the sentence sounds unfinished |
| "One minute / ఒక్క నిమిషం / एक मिनट" | "Sure, take your time", then waits up to `VOICE_HOLD_SECS` (45 s) |
| Caller silent | "Can you hear me?" after `VOICE_SILENCE_SECS` (8 s), then a polite goodbye; no reply at all → `no_response`, retried |
| Voicemail, IVR menu, "switched off / not reachable" | Detected in the first 30 s (6 languages), call ended, outcome `voicemail` / `ivr` / `unreachable`, retried by the dialer |
| Someone else answers / wrong number | No pitch; asks when the lead is free → callback, or Do-Not-Call for wrong numbers |
| Noisy or broken transcript | Asks the caller to repeat instead of guessing |
| Angry, abusive, off-topic, "ignore your instructions" | Stays calm, doesn't argue, returns to topic, never reveals its prompt |
| Call too long | Wrap-up note 45 s before `VOICE_MAX_CALL_SECONDS` (or the AI employee's limit), then a closing line |

**Actions during the call.** The LLM ends a reply with markers that the engine carries out immediately:
`[CALLBACK: YYYY-MM-DD HH:MM]` (new dialer job), `[MEETING: …]` (lead → DEMO_BOOKED, Google Calendar if configured),
`[SEND_WHATSAPP: …]` (WhatsApp if configured, otherwise queued on the lead), `[HUMAN_HANDOFF]`, `[WRONG_PERSON]`,
`[DO_NOT_CALL]` (opt-out list, open jobs cancelled), `[CALL_COMPLETED]`. Safety rules: a reply that ends with a
question never hangs up or books anything; a "we won't call you again" promise always records Do-Not-Call.

**AI employee and knowledge base.** Calls use the live AI employee (or `employee_id`): role, instructions, script,
qualification questions, greeting, voice, max call length and knowledge. Upload documents for it to answer from:
`POST /api/employees/{id}/knowledge` (PDF, Word, Excel, CSV, TXT, MD), `GET` to list, `DELETE …/knowledge/{index}`.

**Analytics and recordings.** Each call stores end reason, interruptions, silence prompts, languages, caller signals,
actions, talk time and reply gaps (`calls.captured.analytics`); `GET /api/analytics/calls?days=30` totals them.
Phone calls are recorded on the server as stereo WAV (caller left, AI right; `VOICE_RECORD_CALLS=off` disables it),
served at `/api/calls/{id}/recording`.

## Outbound calling (dialer)

Upload leads, then **Campaign → Real Phone** (tick the consent box) or `POST /api/dialer/campaigns`.
The dialer (`voice_agent/dialer.py`) queues each lead as a `call_jobs` row and, every second:

1. checks the **calling rules** (`voice_agent/rules.py`):
   - account approved
   - Do-Not-Call / opt-out
   - valid number
   - consent (imported leads need the consent tick)
   - calling hours and days in IST, clamped to 9 AM–9 PM
   - recently called
   - weekly limit
   - optional minimum credit
2. dials through the provider (`voice_agent/outbound.py`), using at most `DIALER_MAX_LINES` lines;
3. moves calls on from provider callbacks:
   - answered → the call runs on the real-time engine → completed (outcome saved);
   - no answer / busy → retry after 2 h, about a day later, then 2 days later → not reachable.

Providers are set with `DIALER_PROVIDER`:
- `vobiz` (also numbers rented from Sarvam)
- `exotel` (needs `EXOTEL_FLOW_URL`, a call flow with the Voicebot applet)
- `fake`: a simulated phone network for testing without a number. Numbers ending in **0** don't
  answer, numbers ending in **9** are busy, and others answer and talk using the fake caller.

Set `VOICE_PUBLIC_BASE_URL` to the public https address the provider calls back on.

Routes:
- `/api/dialer/campaigns`, `/api/dialer/call-now/{lead_id}`, `/api/dialer/status`, `/api/dialer/jobs`
- `/api/dialer/pause|resume|stop`
- The CRM's `/api/campaign/*` buttons use the dialer in Real Phone mode.

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
