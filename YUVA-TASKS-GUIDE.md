# Yuva: Release 1 Task Guide (Data, Leads, Screens)

Hi Yuva, here is how to do each of your Release 1 tasks. Release 1 is **leads + calling only**; campaigns, discovery and WhatsApp/Calendar stay in the code but are hidden until Release 2. Thimothi builds the calling and voice side (Exotel, Pipecat voice engine, rules check, instant-lead webhook, inbound). You build the data, leads, employees, results and all screens.

---

## How We Work (Applies to Every Task)

1. **Start from the latest main:**
   ```bash
   git checkout main && git pull
   git checkout -b feat/y1-routers        # one branch per task: feat/y2-postgres, feat/y3-login ...
   ```
2. **Stay in your folders:** `models/`, `migrations/`, `routers/auth.py`, `routers/leads.py`, `routers/employees.py`, `routers/calls.py`, `routers/admin.py`, `services/postcall.py`, `services/billing.py`, `templates/`, `static/`.
   Thimothi's folders (don't edit): `voice_agent/`, `routers/telephony.py`, `routers/intake.py`, `services/orchestrator.py`, `services/rules.py`.
   Shared files (`main.py`, `requirements.txt`, `.env.example`): keep changes small.
3. **Before opening a PR:** tests pass locally (`pytest`), and the app starts (`uvicorn main:app`).
4. **Open a PR** with: what changed, how to test, and a screenshot for UI changes. Thimothi reviews and merges, and you do the same for his.
5. **Never commit** `.env`, API keys or `.db` files.

---

## Y1: Split `main.py` into Route Files (Week 1)

**Goal:** same app, same URLs, but `main.py` only creates the app and includes routers.

**Steps**
1. Save the current route list, to compare later:
   ```bash
   python -c "import main; print('\n'.join(sorted(f'{sorted(r.methods or [])} {r.path}' for r in main.app.routes)))" > routes_before.txt
   ```
2. Create `routers/__init__.py` and one file per area, each with `router = APIRouter()`:
   | File | Routes to move |
   |---|---|
   | `routers/pages.py` | `GET /` (dashboard HTML) |
   | `routers/leads.py` | `/api/leads/*` (incl. template, export, upload, discover, enrich) |
   | `routers/employees.py` | `/api/employees/*` |
   | `routers/calls.py` | `/api/calls/*` |
   | `routers/campaigns.py` | `/api/campaign/*` (parked for R2) |
   | `routers/integrations.py` | `/api/integrations/*`, `/api/profile`, `/api/tts/test` |
   | `routers/messaging.py` | `/api/messaging/*`, `/api/webhooks/whatsapp`, `/api/calendar/*` |
   | `routers/developer.py` | `/api/v1/*` |
   | `routers/telephony.py` | `/api/call/outbound`, `/telephony/twiml`, `/ws/web-call`, `/ws/telephony`, `/api/telephony/exotel/*`. **Move as-is; Thimothi owns this file after Y1.** |
3. In `main.py`: create the app, middleware, static/templates, then `app.include_router(...)` for each. Replace `@app.on_event("startup")` with a `lifespan` function (it's deprecated).
4. Put the shared `templates = Jinja2Templates(...)` object in a small module (for example `core/web.py`) so routers can import it.
5. Compare: generate `routes_after.txt` the same way, then `diff routes_before.txt routes_after.txt` should be empty.

**Done when:** the diff is empty, all tests pass, and the dashboard works as before.

---

## Y2: Move to PostgreSQL (Week 1)

**Goal:** replace SQLite with Postgres, using SQLAlchemy 2 models and Alembic migrations, plus the new Release 1 tables.

**Steps**
1. Local services (Docker):
   ```bash
   docker run -d --name lc-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=leadcloser -p 5432:5432 postgres:16
   docker run -d --name lc-redis -p 6379:6379 redis:7
   ```
   Add to `.env.example`: `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/leadcloser` and `REDIS_URL=redis://localhost:6379/0`.
2. Add to requirements: `sqlalchemy>=2.0`, `alembic`, `psycopg[binary]`, `phonenumbers`.
3. Create `models/` (one file per table, a shared `Base`). Tables and columns:
   ```
   accounts      id, name, default_language, calling_start(time), calling_end(time),
                 calling_days(int[] 0-6), max_call_seconds, recent_call_hours,
                 calling_approved(bool), rate_per_min(numeric), created_at
   users         id, account_id→accounts, email UNIQUE, password_hash, role(owner|member|admin), created_at
   employees     id, account_id, name, job_type(instant|inbound|bulk), language, voice, tier,
                 greeting, script_steps(jsonb), system_prompt, variables(jsonb),
                 status(draft|testing|live), number_id→numbers NULL, webhook_slug UNIQUE,
                 webhook_secret_hash, created_at, updated_at
   numbers       id, account_id NULL, e164 UNIQUE, provider('exotel'), channels(int),
                 is_test_line(bool), employee_id NULL, status
   leads         id, account_id, employee_id NULL, name, phone_e164, source(manual|csv|webhook|inbound),
                 variables(jsonb), consent_source, opt_out(bool), last_outcome, is_hot(bool),
                 callback_at NULL, notes, created_at, updated_at   UNIQUE(account_id, phone_e164)
   calls         id, account_id, lead_id, employee_id, number_id, direction(out|in),
                 channel(manual|instant|inbound|retry|test), state, provider_call_sid,
                 queued_at, answered_at, ended_at, talk_seconds, billed_blocks, credits(numeric),
                 outcome, sentiment, ended_by, summary, captured(jsonb), transcript(jsonb),
                 recording_url, latency_avg_ms, error
   opt_outs      id, account_id, phone_e164, reason, created_at  UNIQUE(account_id, phone_e164)
   credit_ledger id, account_id, delta(numeric), reason(admin_topup|call|adjust|refund),
                 call_id NULL, note, created_by NULL, created_at   UNIQUE(call_id) WHERE reason='call'
   audit_log     id, account_id, user_id, action, target, details(jsonb), created_at
   ```
   Keep the existing `provider_settings`, `provider_usage_logs` and `ai_employees` data (merge `ai_employees` into `employees`). Use `Numeric` for money (never float) and timezone-aware UTC timestamps.
4. Set up Alembic: `alembic init migrations`, point it at `Base.metadata` and `DATABASE_URL`, then `alembic revision --autogenerate -m "initial"` and `alembic upgrade head`.
5. **Tip, to avoid rewriting everything:** keep the function names in `database.py` (`get_all_leads`, `create_lead`, `save_call_record`, …) but reimplement them with SQLAlchemy sessions. Routers keep working, and you can refactor later.
6. Write `scripts/migrate_sqlite_to_pg.py` to copy existing leads, calls, company_profile (→ account), ai_employees (→ employees) and provider settings.
7. Tests: add `tests/conftest.py` with a fixture that creates a fresh test database (or wraps each test in a transaction and rolls back). No test may depend on another.

**Done when:** `alembic upgrade head` builds the DB, the migration script moves the old data, all tests pass on Postgres, and the app works.

---

## Y3: Login and Account Separation (Week 1)

**Goal:** nobody uses the app or API without logging in, and each account sees only its own data.

**Steps**
1. Add `PyJWT` and `bcrypt` (or `passlib[bcrypt]`). Add `SECRET_KEY` to `.env.example`.
2. `routers/auth.py`:
   - `POST /api/auth/login` (email, password) → JWT (`sub`=user_id, `acc`=account_id, `role`, expiry 12 h)
   - `POST /api/auth/logout`, `GET /api/auth/me`
   - Dashboard pages: store the token in an **httpOnly cookie**. API clients: `Authorization: Bearer`.
3. `core/auth.py`: dependency `get_current_user()` that reads the cookie/header, verifies the JWT and loads the user. Add `require_role("admin")`.
4. Add `Depends(get_current_user)` to **every** router except: login, `/lead-intake/{slug}` (Thimothi, uses its own secret) and Exotel callbacks (Thimothi, use their own secret).
5. **Every query filters by `account_id = user.account_id`.** Do this in the `database.py` functions so it can't be forgotten.
6. Lock the open admin/billing routes now: `/api/v1/keys`, `/api/v1/billing/*`, `/api/integrations/*` → owner/admin only.
7. A login page (`templates/login.html`) that redirects to `/login` when there is no session.
8. `scripts/create_admin.py email password` creates the first account (S P Associates) and an admin user.

**Done when:** APIs return 401 without login, and a test proves user A cannot read account B's leads or calls.

---

## Y4: Clean-Up + Automatic Tests on GitHub (Week 1)

**Steps**
1. **Remove fake results:** delete the "simulation" mode in `services/campaign_service.py` (the hardcoded customer agreement) and hide the Campaigns UI for Release 1.
2. **Tests:**
   - Move dev packages into `requirements-dev.txt`: `pytest`, `pytest-asyncio`, `httpx`.
   - Tests that call the real Sarvam API: `@pytest.mark.skipif(not os.getenv("SARVAM_API_KEY"), reason="needs key")`.
   - Each test uses its own clean data (Y2's fixture).
3. **Pin versions:** after everything works, `pip freeze > requirements.lock` (or pin `fastapi`, `starlette`, `pydantic`, `sqlalchemy` with `==`). Unpinned versions broke the dashboard once already.
4. **GitHub Actions:** `.github/workflows/ci.yml` runs on every push/PR with Python 3.12 + a Postgres service container, runs `alembic upgrade head`, then `pytest -q`.

**Done when:** a fresh clone passes `pytest`, the CI badge is green, and no fake outcomes exist anywhere.

---

## Y5: AI Employee Editor (Weeks 2–3)

**Goal:** an employee page like Outpero's, with tabs.

| Tab | Fields |
|---|---|
| **Setup** | Name · job type (**Instant** / **Inbound**; Bulk visible but "coming soon") · language (te/hi/en) · voice (Sarvam speaker list for that language) · tier (Standard) |
| **Script** | Greeting (with `{name}` etc.) · call steps (ordered list: "1. greet, 2. ask budget, 3. book visit") · objection notes · "Generate from description" button (reuse the existing `employee_builder.py`) |
| **Variables** | Rows: key, label, required, example (e.g. `name`, `project`, `budget`). These are the fields used by the script, CSV columns and the webhook. |
| **Number** | Pick an assigned ExoPhone (from `numbers`); show "test line only" if none |
| **Webhook** (instant only) | Shows `https://<domain>/lead-intake/{webhook_slug}` + secret + sample JSON. The slug/secret generator is provided by Thimothi (T5); until then, show a placeholder. |
| **Test** | Two buttons wired to Thimothi's APIs later: "Talk in browser", "Call my phone" |

**Status rules:** `draft` → `testing` (script saved) → `live` (needs a number + the account approved for calling). Show the status as a pill.
**API:** `GET/POST/PUT/DELETE /api/employees`, `POST /api/employees/{id}/status`.

**Done when:** you can create an instant employee, fill all tabs, attach a number and set it live. Data saved in `employees`.

---

## Y6: Leads (Weeks 2–3)

**Pages and APIs**
1. **Leads list** `GET /api/leads?employee=&outcome=&hot=&callback=&from=&to=&q=&page=`: paginated, 50 per page. Columns: name, phone, employee, last outcome (coloured pill), hot 🔥, callback time, last called, actions.
2. **Add lead:** form (name, phone, employee, variables from that employee, notes, consent source).
3. **Import CSV/Excel:** reuse `excel_service.py`, but:
   - Clean numbers with the `phonenumbers` library, region `IN` (bare 10 digits → +91; remove spaces/dashes).
   - **Reject with a reason:** invalid number, duplicate in file, already exists (update instead), on opt-out list, missing required variable.
   - Show the result: "8 imported, 2 rejected", with a downloadable list of rejected rows and reasons.
   - A required **"I confirm these contacts consented"** checkbox → `consent_source='import_confirmed'`.
4. **Export** CSV/XLSX with the current filters.
5. **Lead detail page:** fields + variables (editable) · **call timeline** (each call: date, outcome, duration, summary, recording player, transcript expandable) · notes · **opt-out toggle** (adds/removes the `opt_outs` row) · **"Call now"** button.
6. **"Call now"** calls Thimothi's `POST /api/leads/{id}/call` (T4). Until it exists, show the button disabled with "Calling available soon". If the API returns a block reason (e.g. "outside calling hours"), show it as a message.

**Done when:** a 10-row CSV with 1 duplicate and 1 bad number → 8 in, 2 rejected with reasons. The detail page shows calls and notes; opt-out works.

---

## Y7: Settings (Week 3)

Stored on the `accounts` table (plus `opt_outs` and `users`).

| Section | Fields |
|---|---|
| Business | Name · default language |
| Calling rules | Start time, end time (default **09:00–21:00 IST**, can't be wider) · calling days (Mon–Sun toggles) · max call length (default 300 s) · "don't call the same number again within N hours" (default 24) |
| Opt-out list | Table + add number + upload CSV + remove |
| Team | List users · invite (email + temporary password + role) · remove |

**API:** `GET/PUT /api/settings`, `GET/POST/DELETE /api/opt-outs`, `GET/POST/DELETE /api/team`.
Thimothi's rules check (T4) **reads these values**, so keep the column names as in Y2.

**Done when:** changes save and reload, and an end time after 21:00 is refused with a clear message.

---

## Y8: After-Call Results (Week 4)

**Goal:** when a call ends, turn the transcript into results on the call and the lead.

1. `services/postcall.py`: function `process_call_end(call_id)`. Thimothi's engine calls it after saving `calls.transcript` (a list of `{role, text, lang, start_ms}`) and `calls.ended_by`.
2. Extend the existing `extract_call_intelligence` prompt to return JSON:
   ```json
   {
     "outcome": "qualified|interested|callback|not_interested|no_response",
     "sentiment": "positive|neutral|negative",
     "summary": "English, 1-2 sentences",
     "captured": { "<variable key>": "<value>" },
     "callback_at": "2026-11-03T18:00:00+05:30 or null",
     "opt_out_requested": true
   }
   ```
   Validate it with a Pydantic model and fall back safely if the JSON is bad. `captured` keys = the employee's variables.
3. Telephony outcomes (`no_answer`, `busy`, `call_failed`, `voicemail`) are set by Thimothi's status webhook (T5) **without** the LLM. Only run the LLM when there was a conversation.
4. Update the lead: `last_outcome`, `is_hot` (qualified/interested within 7 days), `callback_at`, merge `captured` into `variables`. If `opt_out_requested` → add to `opt_outs` and set `lead.opt_out=true`.
5. Then call `charge_call(call_id)` (Y9).

**Done when:** after a test transcript, the call shows outcome + English summary + fields, and the lead shows hot/callback correctly. Test with Telugu and Hindi sample transcripts.

---

## Y9: Credit Tracking (Week 4)

1. `services/billing.py`:
   ```python
   blocks  = ceil(talk_seconds / 30) if talk_seconds > 0 else 0
   credits = blocks * (account.rate_per_min / 2)      # ₹5/min → ₹2.50 per 30 s
   ```
   - Unanswered/busy/failed (`talk_seconds == 0`) → **₹0**, no ledger row.
   - Inbound calls are charged the same way.
   - Insert `credit_ledger(delta=-credits, reason='call', call_id=...)` **in the same transaction** as updating `calls.billed_blocks/credits`.
   - **Idempotent:** the unique index on `call_id` means a repeated webhook can't charge twice.
2. `get_balance(account_id) = SUM(delta)`. Never store or overwrite a balance column.
3. Top bar: show the balance as **minutes** (`balance / rate_per_min`, e.g. "≈ 10 min") plus ₹ on hover. Show "Low balance" under ₹50.
4. Admin top-ups come from Y12 (`reason='admin_topup'`).

**Done when:** 45 s = 2 blocks = ₹5.00 · 20 s = 1 block = ₹2.50 · unanswered = ₹0 · the same call processed twice is charged once (write tests for these).

---

## Y10: Conversations Page (Weeks 5–6)

1. Table of all calls: time, direction (in/out), channel (manual/instant/inbound/retry/test), lead, employee, duration, credits, outcome pill, sentiment, ended_by.
2. Filters: direction, channel, employee, outcome, sentiment, date range, min duration, has recording, plus a search box (name/phone/summary).
3. Row click → side panel: summary, captured fields, **recording player**, transcript (speaker-labelled, language tag).
4. **Recording:** don't expose the Exotel URL directly. Add `GET /api/calls/{id}/recording`, which checks the user's account and then streams the file.
5. **Export CSV** with the current filters.
6. Note on the page: "Recordings kept 90 days" (Thimothi adds the delete job later).

**Done when:** filtering by outcome works, the recording plays, and the CSV matches the filtered rows.

---

## Y11: Dashboard (Week 6)

1. **Top bar (all pages):** live pill "**N on calls · M ringing**" from Thimothi's live feed (T6). WebSocket `/api/live` sends `{call_id, lead_id, employee_id, state}`; keep a small client-side map of active calls. Also the balance in minutes (Y9).
2. **Dashboard body:** today's counters (IST): calls, connected, qualified, credits used · my employees (status, number, calls today) · quick actions (new employee, add lead, import CSV, view conversations) · last 10 calls.
3. A banner "Build your first employee" if there are none (like Outpero).

**Done when:** during a test call, the live pill changes ringing → on call → back to 0, and the counters update.

---

## Y12: Admin Screens (Week 6)

Only for `role=admin`, under `/admin` and `/api/admin/*`.

| Screen | What |
|---|---|
| **Accounts** | List (name, users, balance, calls 7 d, calling approved) · toggle **calling approved** · **add credits** (amount + note → ledger `admin_topup`, plus an `audit_log` row) · view account details |
| **Numbers** | List ExoPhones · add number (e164, channels, test line yes/no) · assign to account/employee · release |
| **Live & health** | All live calls across accounts (from the live feed) · provider health + average latency from Thimothi's `GET /api/admin/health` (T9) |

Log every admin action in `audit_log`.

**Done when:** the admin adds ₹500 → ledger row + new balance + audit entry; approving calling makes the employee "live" possible.

---

## Y13: Pilot Testing (Week 7)

Run these steps from the acceptance test in `RELEASE-1-PLAN.md` §10 and fix what fails:
- 1–7: login, create employee, script/variables, browser test, test call, attach number, CSV import
- 20–25: billing blocks, lead timeline, conversations filter/export, live counter, admin credits, admin live view

Keep a simple bug list (GitHub Issues labelled `pilot`). Fix your UI/data bugs; assign calling/voice bugs to Thimothi.

---

## What You Get from Thimothi (and When)

| Week | From Thimothi | You use it in |
|---|---|---|
| 3 | Transcript format `{role, text, lang, start_ms}` + `ended_by` saved on the call, then a call to `process_call_end(call_id)` | Y8 |
| 4 | `POST /api/leads/{id}/call` (returns `queued` or a block reason) | Y6 "Call now" |
| 4 | Webhook slug + secret generator, talk seconds per call | Y5, Y9 |
| 4 | Live feed WebSocket `/api/live` | Y11, Y12 |
| 6 | `GET /api/admin/health` | Y12 |

## What Thimothi Needs from You (and When)

| Week | From you | He uses it in |
|---|---|---|
| End of week 1 | Final tables (Y2) + login dependency (Y3) | All his routes |
| 2 | Employee fields: script_steps, greeting, language, voice, variables (Y5) | Voice engine prompt |
| 3 | Settings columns: calling hours/days, max_call_seconds, recent_call_hours, opt_outs (Y7) | Rules check |

**Weekly 15-minute check-in:** what's merged, what's blocked, the next hand-off.
