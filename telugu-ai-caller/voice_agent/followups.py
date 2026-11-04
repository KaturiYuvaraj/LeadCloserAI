"""
Follow-ups (Phase B): turns the follow-up engine's plan (services/followup_engine.py,
Plan v2 §4) into dialer jobs, so leads who say "later" are called again until they decide.

  answered, follow-up bucket → next call at the time they asked for, or on the smart cadence
                               (days 1–3 daily at rotating times, then every 2 days, twice a week,
                               weekly WhatsApp after day 30, cold after day 60)
  answered, hot or closed    → no more AI calls (hot leads go to the sales team)
  not answered               → retry +2 h, next day at another time, day-3 evening;
                               then a missed-call WhatsApp and the smart cadence

A callback booked during the call ([CALLBACK]) always wins: it is already a waiting job.
The calling rules (voice_agent/rules.py) still apply to every job: hours, opt-out, weekly limit.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from models import Call, CallJob, Lead
from services.followup_engine import compute_next_followup_step
from services.outcomes import normalize_outcome
from voice_agent.rules import IST, as_utc, db_time

WAITING_STATES = ("queued", "scheduled", "retry_scheduled")
FOLLOWUP_DISPOSITION = "followup"  # CallJob.last_disposition of jobs created here
MISSED_CALL_WHATSAPP = "missed_call: we tried calling you"


def _context(session, lead: Lead, now_utc: datetime) -> Dict[str, Any]:
    """What the follow-up engine needs to know about the lead's call history."""
    rows = session.query(Call.created_at, Call.talk_seconds).filter(Call.lead_id == lead.id).all()
    times: list[tuple[datetime, int]] = []
    for created, talk in rows:
        utc = as_utc(created)
        if utc is not None:
            times.append((utc, int(talk or 0)))
    lead_created = as_utc(lead.created_at) if lead.created_at else None
    first_candidates = [t for t, _ in times] + ([lead_created] if lead_created else [now_utc])
    first = min(first_candidates)
    today_ist = now_utc.astimezone(IST).date()
    answered = sorted([t for t, talk in times if talk > 0])
    return {
        "days_since_first_contact": max(1, (now_utc - first).days + 1),
        "calls_today": sum(1 for t, _ in times if t.astimezone(IST).date() == today_ist),
        "calls_this_week": sum(1 for t, _ in times if now_utc - t < timedelta(days=7)),
        "preferred_pickup_hour": answered[-1].astimezone(IST).hour if answered else None,
    }


def _has_waiting_job(session, lead_id: int) -> bool:
    return session.query(CallJob.id).filter(
        CallJob.lead_id == lead_id, CallJob.state.in_(WAITING_STATES)
    ).first() is not None


def _note_plan(lead: Lead, plan: Dict[str, Any]):
    variables = dict(lead.variables or {})
    variables["followup_plan"] = plan
    lead.variables = variables


def _queue_whatsapp(lead: Lead, what: str):
    variables = dict(lead.variables or {})
    pending = list(variables.get("pending_whatsapp") or [])
    pending.append({"what": what, "at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")})
    variables["pending_whatsapp"] = pending
    lead.variables = variables


def _apply(session, lead: Lead, plan: Dict[str, Any], template: Optional[CallJob]) -> Optional[datetime]:
    """Carry out the plan: WhatsApp now if asked, and a dialer job at next_action_at if it is a call."""
    _note_plan(lead, plan)
    if not plan.get("should_followup"):
        return None
    if plan.get("immediate_action") == "send_whatsapp_brochure":
        _queue_whatsapp(lead, "details / brochure")
    elif plan.get("immediate_action") == "send_missed_call_whatsapp":
        _queue_whatsapp(lead, MISSED_CALL_WHATSAPP)

    channel = plan.get("channel") or ""
    if channel in ("whatsapp_first", "whatsapp_nudge"):
        _queue_whatsapp(lead, "follow-up nudge")
        if channel == "whatsapp_first":
            return None  # days 31–60: WhatsApp first, a call only if they reply
    when = plan.get("next_action_at")
    if not when:
        return None
    when_utc = datetime.fromisoformat(when).astimezone(timezone.utc)
    customer_asked = plan.get("stage") == "fixed_callback"
    session.add(CallJob(
        account_id=lead.account_id, lead_id=lead.id, phone_e164=lead.phone_e164,
        campaign_id=template.campaign_id if template else None,
        language=template.language if template else None,
        provider="pending", state="scheduled", priority=1 if customer_asked else 4,
        attempt=0, max_attempts=2 if customer_asked else 1,
        next_attempt_at=db_time(session, when_utc),
        last_disposition="callback_requested" if customer_asked else FOLLOWUP_DISPOSITION,
        last_error=plan.get("reason"),
    ))
    return when_utc


def after_conversation(session, job: CallJob, outcome: str, now_utc: Optional[datetime] = None
                       ) -> Optional[datetime]:
    """
    The lead answered and the call was saved. Schedule the next follow-up call if the outcome
    asks for one. Returns the time of the next call, or None.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    lead = session.get(Lead, job.lead_id)
    if lead is None or lead.opt_out:
        return None
    if _has_waiting_job(session, lead.id):
        return None  # callback booked during the call
    variables = lead.variables or {}
    label = variables.get("outcome_label") or normalize_outcome(outcome or "")["outcome_label"]
    norm = normalize_outcome(label)
    if norm["outcome_bucket"] == "hot":
        _note_plan(lead, {"should_followup": False, "stage": "with_sales_team", "channel": "none",
                          "next_action_at": None, "reason": "Hot lead: the sales team follows up, not the AI"})
        return None
    plan = compute_next_followup_step(
        outcome_label=label,
        callback_at=variables.get("callback_at"),
        is_opted_out=bool(lead.opt_out),
        is_converted=(variables.get("status") == "CLOSED_WON"),
        now_ist=now_utc.astimezone(IST),
        **_context(session, lead, now_utc),
    )
    return _apply(session, lead, plan, job)


def retry_time(attempt: int, now_utc: Optional[datetime] = None) -> datetime:
    """When to try again after `attempt` unanswered tries: +2 h, next day at another time, day-3 evening."""
    now_utc = now_utc or datetime.now(timezone.utc)
    plan = compute_next_followup_step("no_answer", attempt_number=attempt, consecutive_misses=attempt,
                                      now_ist=now_utc.astimezone(IST))
    return datetime.fromisoformat(plan["next_action_at"]).astimezone(timezone.utc)


def after_unreachable(session, job: CallJob, now_utc: Optional[datetime] = None) -> Optional[datetime]:
    """
    All retries of a job went unanswered. Send a missed-call WhatsApp (once per lead) and
    continue on the smart cadence. Returns the time of the next call, or None.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    lead = session.get(Lead, job.lead_id)
    if lead is None or lead.opt_out or _has_waiting_job(session, lead.id):
        return None
    variables = lead.variables or {}
    if not variables.get("missed_call_whatsapp_at"):
        _queue_whatsapp(lead, MISSED_CALL_WHATSAPP)
        variables = dict(lead.variables or {})
        variables["missed_call_whatsapp_at"] = now_utc.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")
        lead.variables = variables
    context = _context(session, lead, now_utc)
    # The cadence counts from day 4 at the earliest: the not-reachable retries covered days 1–3
    context["days_since_first_contact"] = max(4, context["days_since_first_contact"])
    plan = compute_next_followup_step("busy_no_time", is_opted_out=bool(lead.opt_out),
                                      consecutive_misses=job.attempt, now_ist=now_utc.astimezone(IST),
                                      **context)
    plan["reason"] = f"Not reachable after {job.attempt} tries · {plan.get('reason', '')}".strip(" ·")
    return _apply(session, lead, plan, job)
