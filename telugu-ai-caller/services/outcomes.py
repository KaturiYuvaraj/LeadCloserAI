"""
LeadCloserAI Plan v2 (§3) — Precise 4-Bucket & Outcome Label Taxonomy.

Every call is labeled with:
  - outcome_bucket: "hot" | "follow_up" | "closed" | "not_reachable"
  - outcome_label:  One of the official §3 outcome labels
  - outcome_reason: Why the lead said yes/no/later (e.g., "price", "has_vendor", "no_need", "timing")
  - callback_at:    IST datetime when a callback was requested
  - confidence:     0.0–1.0 (below 0.70 goes to the human review list)
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

IST = timezone(timedelta(hours=5, minutes=30))

CONFIDENCE_REVIEW_THRESHOLD = 0.70

OUTCOME_BUCKETS = {
    "hot": {
        "title": "Hot",
        "icon": "🔥",
        "description": "Ready for quotation, meeting, or immediate rep action",
    },
    "follow_up": {
        "title": "Follow-up",
        "icon": "⏳",
        "description": "Callback scheduled or nurturing on smart cadence",
    },
    "closed": {
        "title": "Closed",
        "icon": "❌",
        "description": "Not interested, Do-Not-Call, or invalid lead",
    },
    "not_reachable": {
        "title": "Not reachable",
        "icon": "📵",
        "description": "No answer, busy, switched off, voicemail, or invalid number",
    },
}

OUTCOME_CATALOG: Dict[str, Dict[str, Any]] = {
    # 🔥 Hot bucket
    "interested_now": {
        "bucket": "hot",
        "display": "Interested Now",
        "next_step": "Quotation + meeting + rep alert",
        "legacy_stage": "closed_won",
        "crm_status": "QUALIFIED",
        "is_hot": True,
        "opt_out": False,
    },
    "meeting_booked": {
        "bucket": "hot",
        "display": "Meeting Booked",
        "next_step": "Calendar invite + reminders",
        "legacy_stage": "demo_scheduled",
        "crm_status": "DEMO_BOOKED",
        "is_hot": True,
        "opt_out": False,
    },
    "human_requested": {
        "bucket": "hot",
        "display": "Human Requested",
        "next_step": "Rep calls within 15 min target; live transfer if free",
        "legacy_stage": "qualified",
        "crm_status": "QUALIFIED",
        "is_hot": True,
        "opt_out": False,
    },
    # ⏳ Follow-up bucket
    "callback_scheduled": {
        "bucket": "follow_up",
        "display": "Callback Scheduled",
        "next_step": "Call at exact requested time",
        "legacy_stage": "follow_up",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "interested_later": {
        "bucket": "follow_up",
        "display": "Interested Later",
        "next_step": "Call on target future date",
        "legacy_stage": "follow_up",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "send_details_first": {
        "bucket": "follow_up",
        "display": "Send Details First",
        "next_step": "WhatsApp brochure now -> call in 1 day",
        "legacy_stage": "follow_up",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "decision_maker": {
        "bucket": "follow_up",
        "display": "Decision Maker Needed",
        "next_step": "Ask for joint call slot or partner's number",
        "legacy_stage": "follow_up",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "busy_no_time": {
        "bucket": "follow_up",
        "display": "Busy (No Time Given)",
        "next_step": "Smart cadence follow-up (§4)",
        "legacy_stage": "follow_up",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    # ❌ Closed bucket
    "not_interested": {
        "bucket": "closed",
        "display": "Not Interested",
        "next_step": "Stop calling; optional 90-day re-check",
        "legacy_stage": "lost",
        "crm_status": "LOST",
        "is_hot": False,
        "opt_out": False,
    },
    "do_not_call": {
        "bucket": "closed",
        "display": "Do Not Call",
        "next_step": "Added to opt-out list, never called again",
        "legacy_stage": "lost",
        "crm_status": "LOST",
        "is_hot": False,
        "opt_out": True,
    },
    "wrong_person": {
        "bucket": "closed",
        "display": "Wrong Person",
        "next_step": "Stop; reported to marketing as bad lead",
        "legacy_stage": "lost",
        "crm_status": "LOST",
        "is_hot": False,
        "opt_out": True,
    },
    "invalid_lead": {
        "bucket": "closed",
        "display": "Invalid Lead",
        "next_step": "Stop; reported to marketing as bad lead",
        "legacy_stage": "lost",
        "crm_status": "LOST",
        "is_hot": False,
        "opt_out": True,
    },
    # 📵 Not reachable bucket
    "no_answer": {
        "bucket": "not_reachable",
        "display": "No Answer",
        "next_step": "Retries at different times + missed-call WhatsApp",
        "legacy_stage": "no_answer",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "busy": {
        "bucket": "not_reachable",
        "display": "Line Busy",
        "next_step": "Retries at different times + missed-call WhatsApp",
        "legacy_stage": "busy",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "switched_off": {
        "bucket": "not_reachable",
        "display": "Switched Off",
        "next_step": "Retries at different times + missed-call WhatsApp",
        "legacy_stage": "no_answer",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "voicemail": {
        "bucket": "not_reachable",
        "display": "Voicemail",
        "next_step": "Retries at different times + missed-call WhatsApp",
        "legacy_stage": "no_answer",
        "crm_status": "CONTACTED",
        "is_hot": False,
        "opt_out": False,
    },
    "invalid_number": {
        "bucket": "not_reachable",
        "display": "Invalid Number",
        "next_step": "Stop; reported to marketing",
        "legacy_stage": "failed",
        "crm_status": "LOST",
        "is_hot": False,
        "opt_out": True,
    },
}

LEGACY_TO_V2_MAP: Dict[str, str] = {
    "closed_won": "interested_now",
    "qualified": "interested_now",
    "interested": "interested_now",
    "hot": "interested_now",
    "demo_scheduled": "meeting_booked",
    "demo_booked": "meeting_booked",
    "follow_up": "callback_scheduled",
    "callback": "callback_scheduled",
    "qualifying": "busy_no_time",
    "contacted": "busy_no_time",
    "lost": "not_interested",
    "no-answer": "no_answer",
    "no_response": "no_answer",
    "failed": "no_answer",
    "call_failed": "no_answer",
}


def normalize_outcome(
    raw_outcome: Optional[str],
    transcript_text: str = "",
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Map any outcome label or legacy deal_stage into the official Plan v2 (§3)
    outcome_label, outcome_bucket, display name, next_step, and flags.
    """
    key = (raw_outcome or "").strip().lower().replace(" ", "_").replace("-", "_")
    lower_tx = (transcript_text or "").lower()

    # Check transcript hints for specific sub-labels when generic stage is given
    if key not in OUTCOME_CATALOG:
        if any(p in lower_tx for p in ["don't call", "dont call", "never call", "stop calling", "కాల్ చేయకండి", "ఫోన్ చేయకండి", "कॉल मत करना", "फोन मत करो"]):
            key = "do_not_call"
        elif any(p in lower_tx for p in ["wrong number", "never enquired", "రాంగ్ నంబర్", "गलत नंबर"]):
            key = "wrong_person"
        elif any(p in lower_tx for p in ["senior", "manager", "human", "person call", "మేనేజర్", "सीनियर"]):
            key = "human_requested"
        elif any(p in lower_tx for p in ["send on whatsapp", "whatsapp details", "brochure", "వాట్సాప్ లో పంపండి", "व्हाट्सएप पर भेज"]):
            key = "send_details_first"
        elif any(p in lower_tx for p in ["partner decides", "ask my partner", "husband", "director", "పార్ట్నర్", "पार्टनर"]):
            key = "decision_maker"
        elif any(p in lower_tx for p in ["next month", "after diwali", "after sankranti", "వచ్చే నెల", "अगले महीने"]):
            key = "interested_later"
        else:
            key = LEGACY_TO_V2_MAP.get(key, "busy_no_time")

    meta = OUTCOME_CATALOG[key]
    conf = float(confidence) if confidence is not None else 0.85
    conf = max(0.0, min(1.0, conf))

    return {
        "outcome_label": key,
        "outcome_bucket": meta["bucket"],
        "bucket_title": OUTCOME_BUCKETS[meta["bucket"]]["title"],
        "bucket_icon": OUTCOME_BUCKETS[meta["bucket"]]["icon"],
        "display_label": meta["display"],
        "next_step": meta["next_step"],
        "legacy_stage": meta["legacy_stage"],
        "crm_status": meta["crm_status"],
        "is_hot": meta["is_hot"],
        "opt_out_requested": meta["opt_out"],
        "confidence": round(conf, 2),
        "needs_human_review": conf < CONFIDENCE_REVIEW_THRESHOLD,
    }


def parse_callback_time_ist(
    raw_value: Optional[str],
    now_utc: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Convert an ISO timestamp or natural callback phrase ("tomorrow 6 PM",
    "tomorrow 11 AM", "in 2 hours", "next Monday") into a timezone-aware IST datetime.
    """
    if not raw_value or not isinstance(raw_value, str):
        return None
    text = raw_value.strip()
    if not text or text.lower() in {"null", "none", "n/a", "not specified"}:
        return None

    # 1. Try ISO 8601 parsing first
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except ValueError:
        pass

    base_ist = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    lower = text.lower()

    # Extract hour if present (e.g. "6 pm", "11 am", "18:00", "11:30")
    hour = 11
    minute = 0
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
    if time_match:
        h = int(time_match.group(1))
        m = int(time_match.group(2) or 0)
        meridiem = (time_match.group(3) or "").lower()
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        elif not meridiem and 1 <= h <= 7:
            h += 12  # business hours assumption for 1..7 without am/pm
        if 0 <= h <= 23 and 0 <= m <= 59:
            hour, minute = h, m

    if "tomorrow" in lower or "రేపు" in lower or "कल" in lower:
        target_day = (base_ist + timedelta(days=1)).date()
        return datetime(target_day.year, target_day.month, target_day.day, hour, minute, tzinfo=IST)

    in_hours = re.search(r"in\s+(\d+)\s*hour", lower)
    if in_hours:
        return base_ist + timedelta(hours=int(in_hours.group(1)))

    in_days = re.search(r"in\s+(\d+)\s*day", lower)
    if in_days:
        target_day = (base_ist + timedelta(days=int(in_days.group(1)))).date()
        return datetime(target_day.year, target_day.month, target_day.day, hour, minute, tzinfo=IST)

    if "next month" in lower or "వచ్చే నెల" in lower or "अगले महीने" in lower:
        target_day = (base_ist + timedelta(days=30)).date()
        return datetime(target_day.year, target_day.month, target_day.day, 11, 0, tzinfo=IST)

    return None

