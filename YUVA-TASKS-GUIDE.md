# LeadCloserAI: Lead-to-Revenue Automation Plan (v2) & Developer Task Guide

> **For:** S P Associates (management, sales, digital marketing team) + developers (`thimothi306`, `Yuva`) · 3 Nov 2026  
> **v2:** Reviewed against the current code, real calling behaviour in India, cost and compliance. **This is the single plan to work from.** It replaces the open items in `RELEASE-1-PLAN`, `WORK-SPLIT` and the previous Y/T task guides (see §11 for the mapping).

---

## 0. What Changed from v1

| # | Gap in v1 | Fixed in v2 |
|---|---|---|
| 1 | Skipped the **foundation**: there's no real outbound dialling yet, and the campaign button runs a **fake simulation** | New **Phase 0**: real dialling, campaign queue, rules check, retries, remove the fake simulation |
| 2 | Only 3 outcomes; ignored leads who **don't pick up** (often 40–60% of dials) | 4 buckets: **Hot · Follow-up · Closed · Not reachable**, plus a precise outcome list (§3) |
| 3 | "Call every day until they convert" risks **spam flags, complaints and cost** | Smart cadence with caps, channel mix (WhatsApp first where it fits), weekly limit per number, number health (§4) |
| 4 | AI could send prices freely | Quotation guardrails: price book only, discount limits, manager approval for custom scope (§5) |
| 5 | WhatsApp rules not covered | Opt-in during the call, approved templates, 24-hour window, STOP handling (§6) |
| 6 | No human follow-through on hot leads | Rep response time target, escalation, live transfer, lead assignment rules (§7) |
| 7 | No numbers | Cost per lead estimate and KPIs with targets (§9) |
| 8 | No safe rollout | **Pilot** with 50 → 200 → all leads, plus quality review (§10) |
| 9 | Login missing before the team uses it | Login and roles moved into Phase 0 |
| 10 | Three separate task lists (Y, T, plan phases) | **One backlog**, mapped to owners (§11) |

---

## 1. Where We Are Today (Checked Against the Code)

| Capability | Status |
|---|---|
| Upload Excel/CSV, find columns, skip duplicates | ✅ Works |
| Real-time AI voice engine (1.3–2 s replies, interruptions, Telugu/Hindi/English/Tamil/Kannada/Malayalam, auto-hangup) | ✅ Works: browser + phone path |
| Phone providers: Exotel, Vobiz, Sarvam-rented numbers (inbound/stream) | ✅ Built, tested with the fake caller; waiting for a real number |
| **AI dials out to a client's phone** | ✅ Built (`voice_agent/outbound.py`, `voice_agent/dialer.py`, `routers/dialer.py`) |
| Campaign queue with rules (hours, DND, consent, retries) | ✅ Built (`voice_agent/rules.py`, `voice_agent/dialer.py`); UI wired to real queue & fake simulation removed in Phase 0 |
| Sorting calls into 4 buckets + 13 outcomes + follow-up engine | 🔄 Phase 0 & Phase B (4-bucket & 13-outcome taxonomy in `services/outcomes.py`) |
| Quotations, WhatsApp, meetings | ⏳ Phase C & Phase D (Price book, PDF generator, WhatsApp templates, Calendar) |
| Login, roles, admin pipeline | ✅ Phase 0 (`core/auth.py`, `routers/auth.py`, `templates/login.html`, `scripts/create_admin.py`) & Phase E |

---

## 2. The Journey

```
 LEAD SOURCES ── CSV · Excel · Google Sheet · paste · Meta/Google lead forms · website
 │               forms · IndiaMART/JustDial · email · Zapier/Pabbly · API
 ▼
 IMPORT & CLEAN ── column mapping (AI-assisted) · +91 cleanup · duplicates merged ·
 │                 source/campaign/marketer tags · consent · DND check · import report
 ▼
 CAMPAIGN QUEUE ── rules check (9 AM–9 PM, days, holidays, DND, consent, credit,
 │                 weekly limit) · lines available · priority (new form leads first)
 ▼
 AI CALL ── greeting + recording/AI notice · qualify · handle objections ·
 │          capture budget/timeline/need · ask WhatsApp permission · close
 ▼
 OUTCOME (one of 4 buckets, §3)
 ├─ 🔥 HOT ───────── quotation → WhatsApp + stored · meeting booked · rep alerted
 │                    (response target) · AI follows up on the quote · Won/Lost
 ├─ ⏳ FOLLOW-UP ──── callback at the time they said · smart cadence · WhatsApp
 │                    nudges · AI remembers last talk · until yes / clear no / cap
 ├─ ❌ CLOSED ─────── reason recorded · Do-Not-Call honoured forever ·
 │                    optional polite re-check after 90 days (only if allowed)
 └─ 📵 NOT REACHABLE ─ retries at different times · missed-call WhatsApp ·
                      wrong/invalid numbers flagged back to marketing
 ▼
 ADMIN PANEL ── pipeline board · today's follow-ups · source performance ·
 │              quotes · meetings · reasons · rep performance · daily digest
 ▼
 FEEDBACK TO ADS ── interested/won results sent to Meta & Google so ads find
                    better leads · bad sources flagged
```

---

## 3. Outcomes: Precise, Not Guessed

The AI labels every call with **one outcome**, a **reason**, **captured details** and, when relevant, a **callback time**. Unsure labels (low confidence) go to a **human review** list. Reps can always correct a label; the change is logged.

| Bucket (admin panel) | Outcome label | Example | Next step |
|---|---|---|---|
| 🔥 **Hot** (`hot`) | `interested_now` | "Send me the quotation", "Let's meet" | Quotation + meeting + rep alert |
| | `meeting_booked` | Agreed a slot on the call | Calendar invite + reminders |
| | `human_requested` | "Can someone senior call me?" | Rep calls within the target time; live transfer if a rep is free |
| ⏳ **Follow-up** (`follow_up`) | `callback_scheduled` | "Call me tomorrow at 6" | Call at exactly that time |
| | `interested_later` | "Next month", "after Diwali" | Call on that date |
| | `send_details_first` | "Send it on WhatsApp, I'll check" | WhatsApp brochure now → call in 1 day |
| | `decision_maker` | "My partner decides" | Ask for a joint call slot or the partner's number |
| | `busy_no_time` | "Busy now", no time given | Smart cadence (§4) |
| ❌ **Closed** (`closed`) | `not_interested` (+ reason: price, has vendor, no need, timing…) | Clear no | Stop calling; optional 90-day re-check |
| | `do_not_call` | "Don't call again" | Opt-out list, never called again |
| | `wrong_person` / `invalid_lead` | "I never enquired", wrong person | Stop; reported to marketing as a bad lead |
| 📵 **Not reachable** (`not_reachable`) | `no_answer`, `busy`, `switched_off`, `voicemail` | — | Retries at different times + missed-call WhatsApp |
| | `invalid_number` | Number doesn't exist | Stop; reported to marketing |

**The 40 / 30 / 30 split** you see today is **for connected calls**. The system measures the real split per source and campaign, so it's never assumed.

---

## 4. Follow-Up Engine: Persistent but Respectful

**Callback times are taken from the call** ("tomorrow 6 PM", "next Monday", "after the 15th"), converted to a date and time (IST) and confirmed in the AI's reply: "Sure, I'll call you tomorrow at 6 PM."

**Smart cadence** (default; the admin can edit it per campaign):

| Stage | When | How |
|---|---|---|
| Days 1–3 | Once a day, **rotating** morning / afternoon / evening | AI call |
| Days 4–10 | Every 2 days, at the hour they picked up before | AI call; WhatsApp nudge if 2 calls in a row are missed |
| Days 11–30 | Twice a week | AI call or WhatsApp (whichever they respond to) |
| Days 31–60 | Weekly | WhatsApp first, call if they reply |
| After 60 days | Stop → **Cold** (shown in admin; can be restarted) | — |

**Not reachable:** retry after 2 h → next day at a different time → day 3 evening → after 3 misses, WhatsApp "we tried calling…" → then the follow-up cadence above.

**Safeguards:**
- **Never** outside 9 AM–9 PM IST, on blocked days or holidays; at most **1 call a day** per lead (unless they asked for a time), and at most **4 calls a week**.
- An instant stop on "don't call", on WhatsApp "STOP", or when the lead converts.
- **Caller memory:** each follow-up starts from the last conversation: "Last week you said the budget was ₹40,000 and you'd decide after Diwali."
- **Number health:** rotate outbound numbers, watch answer rates (a sudden drop means the number is being flagged as spam), register the business caller ID with Truecaller, keep DLT registration current.

---

## 5. Hot Leads → Quotation → Meeting → Won

1. **On the call:** confirm the need and budget, **ask permission to WhatsApp** ("Shall I send the quotation to this number on WhatsApp?"), offer two meeting slots.
2. **Quotation** built from the **price book** + captured requirements:
   - standard packages → sent **automatically**
   - custom scope or a discount above the limit → **manager approval** first (one tap in the admin panel or on WhatsApp)
   - branded PDF with quote number, validity, terms, GST; **stored with versions**
3. **WhatsApp** (approved template with the PDF) plus optional email; **opened / read status** tracked.
4. **Meeting** in the rep's Google Calendar (Meet link or phone), with reminders **1 day and 1 hour** before; **no-show** → automatic reschedule attempt.
5. **Rep alerted immediately** with a one-line brief: "🔥 Ramesh · e-commerce · ₹50k · wants a demo Sat 11 AM · quote Q-1042 sent".
6. **Quote follow-up:** not opened in 24 h → WhatsApp; no reply in 48 h → AI call; expiring → reminder.
7. **Close:** Won (amount, optional Razorpay advance link) or Lost (reason).

---

## 6. WhatsApp Done Right

- **Business API** (Meta Cloud API or a provider like Interakt/AiSensy). The normal WhatsApp app can't be automated.
- **Opt-in** is captured on the call ("Shall I send it on WhatsApp?") or from the lead form; stored with the time.
- **Templates approved by Meta** before use: quotation (with PDF), meeting confirmation, reminder, missed-call note, follow-up nudge.
- **The 24-hour window:** after the client replies, free-form messages are allowed for 24 h; otherwise only templates.
- **"STOP"** replies → opt-out from WhatsApp **and** calls.
- Marketing-type templates cost more than utility ones; quotes and reminders count as **utility**, so they're cheaper.

---

## 7. People in the Loop

- **Assignment rules:** by service, region, language or round robin; workload limits per rep.
- **Response target:** a rep acts on a hot lead within **15 minutes** in working hours; if not, **escalate** to the manager.
- **Live transfer:** if the lead asks for a person and a rep is free, the AI transfers the call.
- **Override and audit:** reps can change any stage or outcome; every change is logged.
- **Human review list:** low-confidence outcomes and complaints are checked daily.

---

## 8. Admin Panel

| Screen | Purpose |
|---|---|
| **Pipeline board** | The 4 buckets + deal stages (Quote sent · Meeting · Negotiation · Won · Lost) with counts; filters: source, campaign, marketer, rep, date, language |
| **Today's work** | Follow-ups due today, callbacks at fixed times, hot leads waiting for a rep, quotes waiting for approval |
| **Source performance** (marketing) | Per source and campaign: leads → reached → hot → quotes → meetings → won → **revenue**, **cost per lead**, **cost per customer**, bad/invalid lead % |
| **Quotations** | Sent / opened / accepted / expired, value, by rep |
| **Meetings** | Upcoming, done, no-shows |
| **Reasons** | Why leads say no or delay, trends by week |
| **Lead timeline** | Every call (recording, transcript, summary), WhatsApp message, quote, meeting and note |
| **Team** | AI vs rep handled, response times, conversion per rep |
| **Daily digest** | Evening WhatsApp to the owner with the day's numbers |

---

## 9. Cost and KPIs

**Cost example** (estimate; real rates once the phone provider is confirmed):
1,000 new leads a month, first call about 1.5 connected minutes; about 300 follow-up leads with about 5 more calls of about 1 minute; Sarvam services + phone about ₹1.9/min:
- calls ≈ (1,000 × 1.5 + 300 × 5 × 1) = **3,000 min × ₹1.9 ≈ ₹5,700**
- WhatsApp templates (about 2,000 utility messages) ≈ **₹300–1,600**
- numbers ≈ **₹120–320**
- **≈ ₹6,000–7,500 a month ≈ ₹6–8 per lead**, all leads called, followed up and sorted

**KPIs to track from day 1:**

| KPI | Pilot target |
|---|---|
| New form lead → first call | < 60 s (goal 30 s) |
| Reach rate (connected / leads) | > 60% after retries |
| AI reply gap | < 2 s |
| Outcome label accuracy (spot-check 50 calls) | > 90% |
| Hot lead → rep action | < 15 min |
| Follow-up calls made on time | > 95% |
| Complaints / opt-outs | < 2% of leads |
| Cost per lead | < ₹10 |

---

## 10. Rollout: Pilot Before Scaling

1. **Internal test:** the team acts as customers (Telugu/Hindi/English/Tamil/Kannada/Malayalam); fix the script.
2. **Pilot 50 real leads** from one source, recording on, **every call reviewed** by a person.
3. **Pilot 200 leads** from 2–3 sources; check the KPIs above; tune the cadence and quotation flow.
4. **All leads**, with weekly reviews of the reasons, the KPIs and 20 random calls.

---

## 11. One Backlog (Replaces the Separate Lists)

| Phase | What | Owner | Effort | Old task IDs |
|---|---|---|---|---|
| **0. Foundation** | Login + roles · **outbound dialling** via provider → new engine · campaign queue with lines/pacing · rules check · retries · **remove the fake simulation** · outcome labels stored | thimothi: dialling, queue, rules, retries · Yuva: login, roles, remove the simulation, outcome labels | **1–1.5 wk** | T4, T5, Y3, Y4 |
| **A. Leads in** | Import from Excel/CSV/Google Sheet/paste with AI column mapping, source tags, consent, import report, rejected rows | Yuva | 1 wk | Y6 |
| **B. Outcomes + follow-ups** | Outcome classifier (§3) with callback time + confidence · follow-up engine (§4) · caller memory · human review list | thimothi | 1–1.5 wk | Y8, T3/T8 leftovers |
| **C. Quotation + WhatsApp** | Price book, quotation PDF, approval, WhatsApp templates + opt-in + STOP, quote follow-up | Yuva: price book, PDF, screens · thimothi: WhatsApp, in-call trigger | 1.5 wk | (new) |
| **D. Meetings + people** | Calendar booking in the call, reminders, no-show recovery, assignment rules, response-target escalation, live transfer | thimothi | 1–1.5 wk | (new) |
| **E. Admin panel** | Pipeline board, today's work, source performance, quotes, meetings, reasons, team, daily digest | Yuva | 1.5 wk | Y10–Y12 |
| **F. Marketing connectors** | Meta/Google lead webhooks (instant call), send results back to ads, IndiaMART/JustDial, email lead parser | thimothi | 1.5–2 wk | T7 |
| **G. SaaS** | Multiple companies, agency/white-label mode, self sign-up, credits + 30-second billing + GST invoices, templates per industry | Both | 3–4 wk | Y9, T10 |

**Critical path to the first real pilot:** phone number (Sarvam/Exotel) + **Phase 0** + Phase A (mostly exists) + Phase B → **about 3 weeks**.

---

## 12. Risks and How We Handle Them

| Risk | Mitigation |
|---|---|
| Number flagged as spam (Truecaller, telco) | Rotate numbers, caps per lead, answer-rate monitoring, Truecaller business registration, consented leads only |
| AI promises a wrong price | Price book only, discount limits, manager approval for custom quotes, "our team will confirm" fallback |
| Wrong outcome label → lead lost or over-called | Confidence threshold → human review; reps can override; weekly accuracy check |
| Phone provider outage | Two providers ready (Exotel + Vobiz/Sarvam); calls pause and retry automatically |
| Legal (TRAI/DND, DPDP) | DND check, consent record, recording/AI notice, opt-out everywhere, data deletion, India-hosted data |
| Cost overrun | Daily spend cap per campaign, follow-up caps, cost dashboard |

---

## 13. Ideas for Later

- **WhatsApp AI assistant** answering replies and rescheduling.
- **Inbound AI receptionist** on the business number (engine ready).
- **Knowledge base** from brochures and price lists for detailed questions.
- **Script A/B tests** and AI call-quality scoring.
- **Lead scoring** (hot/warm/cold) and a **revenue forecast**.
- **After winning:** onboarding calls, payment reminders, review/referral requests, renewal reminders. The same engine keeps working for the customer relationship.

---

## 14. Needed from S P Associates

1. **Price book:** services, packages, prices, GST, the maximum discount the AI may offer, what needs approval.
2. **Current quotation format** (logo, terms, validity, bank details).
3. **Follow-up preferences:** cadence OK as in §4? Calling hours, blocked days, holidays.
4. **Sales team:** names, numbers, calendars, assignment rules, the response target for hot leads.
5. **Lead sources** used by the marketing team + **a sample file from each**.
6. **Definition of "won"** (advance paid / agreement signed).
7. Allowed to re-contact "not interested" leads after 90 days?
8. **Accounts:** WhatsApp Business API, Meta developer app, Google Workspace/Calendar, phone number (in progress).
