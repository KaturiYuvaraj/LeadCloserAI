"""
Follow-Up Engine: Persistent but Respectful (Plan v2 §4).

Implements:
1. Caller Memory injection so follow-up calls resume from the last conversation
   ("Last time we spoke you mentioned a budget of ₹40,000...").
2. Smart Cadence schedule:
   - Days 1–3: Once a day, rotating morning (10:30) / afternoon (14:30) / evening (18:30) IST -> AI call
   - Days 4–10: Every 2 days, at the hour they picked up before -> AI call (WhatsApp nudge if 2 misses in a row)
   - Days 11–30: Twice a week (+3 days) -> AI call or WhatsApp
   - Days 31–60: Weekly (+7 days) -> WhatsApp first, call if they reply
   - After 60 days: Stop -> Cold (shown in admin; can be restarted)
3. Not-Reachable Retry Schedule:
   - Miss 1: retry after +2 hours
   - Miss 2: next day at a different time slot
   - Miss 3: Day 3 evening + missed-call WhatsApp ("We tried calling...") -> then smart cadence
4. Safeguards:
   - Strictly 9:00 AM–9:00 PM IST
   - Max 1 call/day per lead (unless customer requested a fixed callback time)
   - Max 4 calls/week per lead
   - Instant stop on opt-out, do_not_call, not_interested, invalid_number, or converted
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from services.outcomes import normalize_outcome, parse_callback_time_ist

IST = timezone(timedelta(hours=5, minutes=30))

ROTATING_SLOTS_IST = [
    ("morning", 10, 30),
    ("afternoon", 14, 30),
    ("evening", 18, 30),
]

STOP_OUTCOMES = {
    "do_not_call",
    "not_interested",
    "wrong_person",
    "invalid_lead",
    "invalid_number",
}


def clamp_to_calling_hours_ist(dt: datetime, start_hour: int = 9, end_hour: int = 21) -> datetime:
    """
    Ensures any scheduled timestamp falls strictly within 09:00–21:00 IST.
    If before 9 AM, moves to 10:00 AM same day.
    If at/after 9 PM, moves to 10:00 AM next day.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    if dt.hour < start_hour:
        return dt.replace(hour=10, minute=0, second=0, microsecond=0)
    if dt.hour >= end_hour:
        next_day = dt + timedelta(days=1)
        return next_day.replace(hour=10, minute=0, second=0, microsecond=0)
    return dt


def compute_next_followup_step(
    outcome_label: str,
    callback_at: Optional[str] = None,
    days_since_first_contact: int = 0,
    attempt_number: int = 1,
    consecutive_misses: int = 0,
    preferred_pickup_hour: Optional[int] = None,
    calls_today: int = 0,
    calls_this_week: int = 0,
    is_opted_out: bool = False,
    is_converted: bool = False,
    now_ist: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Computes the next follow-up action, channel, stage, and scheduled IST timestamp
    according to Plan v2 §4.
    """
    now = now_ist.astimezone(IST) if (now_ist and now_ist.tzinfo) else (
        now_ist.replace(tzinfo=IST) if now_ist else datetime.now(IST)
    )
    norm = normalize_outcome(outcome_label)
    label = norm["outcome_label"]
    bucket = norm["outcome_bucket"]

    # 1. Instant Stop Safeguards
    if is_opted_out or label == "do_not_call":
        return {
            "should_followup": False,
            "stage": "stopped_opt_out",
            "channel": "none",
            "next_action_at": None,
            "reason": "Lead opted out / Do-Not-Call honoured forever",
        }

    if is_converted:
        return {
            "should_followup": False,
            "stage": "stopped_converted",
            "channel": "none",
            "next_action_at": None,
            "reason": "Lead already converted (Won)",
        }

    if label in STOP_OUTCOMES:
        return {
            "should_followup": False,
            "stage": "closed",
            "channel": "none",
            "next_action_at": None,
            "recheck_after_days": 90 if label == "not_interested" else None,
            "reason": f"Closed outcome ({label}); automatic calling stopped",
        }

    # 2. 60-Day Cap -> Cold
    if days_since_first_contact > 60:
        return {
            "should_followup": False,
            "stage": "cold",
            "channel": "none",
            "next_action_at": None,
            "reason": "Reached 60-day follow-up cap; moved to Cold (can be restarted in Admin)",
        }

    # 3. Fixed-time callback requested by customer ("Call me tomorrow at 6 PM")
    if label in {"callback_scheduled", "interested_later"} and callback_at:
        parsed_dt = parse_callback_time_ist(callback_at, now_utc=now)
        if parsed_dt:
            target_dt = clamp_to_calling_hours_ist(parsed_dt)
            return {
                "should_followup": True,
                "stage": "fixed_callback",
                "channel": "ai_call",
                "next_action_at": target_dt.isoformat(),
                "slot_name": "customer_requested",
                "reason": f"Customer requested callback at {target_dt.strftime('%Y-%m-%d %H:%M IST')}",
            }

    # 4. Weekly Cap Safeguard (max 4 calls/week unless customer requested fixed callback)
    if calls_this_week >= 4:
        days_until_next_week = max(1, 7 - now.weekday())
        next_week_dt = clamp_to_calling_hours_ist(
            (now + timedelta(days=days_until_next_week)).replace(hour=10, minute=30, second=0, microsecond=0)
        )
        return {
            "should_followup": True,
            "stage": "weekly_cap_deferred",
            "channel": "whatsapp_nudge",
            "next_action_at": next_week_dt.isoformat(),
            "reason": "Max 4 calls/week cap reached; deferred next call to next week",
        }

    # 5. Send Details First ("Send it on WhatsApp, I'll check") -> WhatsApp now + Call in 1 day
    if label == "send_details_first":
        next_dt = clamp_to_calling_hours_ist(now + timedelta(days=1))
        return {
            "should_followup": True,
            "stage": "details_sent_followup",
            "channel": "ai_call",
            "immediate_action": "send_whatsapp_brochure",
            "next_action_at": next_dt.isoformat(),
            "reason": "Send WhatsApp brochure immediately and follow up by phone in 24 hours",
        }

    # 6. Not Reachable Schedule (no_answer, busy, switched_off, voicemail)
    if bucket == "not_reachable":
        misses = max(1, consecutive_misses)
        if misses == 1:
            # Retry after 2 hours (clamped to 9 AM - 9 PM IST)
            next_dt = clamp_to_calling_hours_ist(now + timedelta(hours=2))
            return {
                "should_followup": True,
                "stage": "not_reachable_retry_1",
                "channel": "ai_call",
                "next_action_at": next_dt.isoformat(),
                "reason": "1st miss: retry after 2 hours",
            }
        elif misses == 2:
            # Next day at a different rotating time slot
            slot_name, hr, mn = ROTATING_SLOTS_IST[attempt_number % len(ROTATING_SLOTS_IST)]
            next_dt = (now + timedelta(days=1)).replace(hour=hr, minute=mn, second=0, microsecond=0)
            return {
                "should_followup": True,
                "stage": "not_reachable_retry_2",
                "channel": "ai_call",
                "slot_name": slot_name,
                "next_action_at": next_dt.isoformat(),
                "reason": f"2nd miss: retry next day ({slot_name})",
            }
        else:
            # Day 3 evening + missed-call WhatsApp after 3 misses
            next_dt = (now + timedelta(days=1)).replace(hour=18, minute=30, second=0, microsecond=0)
            return {
                "should_followup": True,
                "stage": "not_reachable_retry_3_whatsapp",
                "channel": "missed_call_whatsapp_then_cadence",
                "immediate_action": "send_missed_call_whatsapp",
                "slot_name": "evening",
                "next_action_at": next_dt.isoformat(),
                "reason": "3 misses: send missed-call WhatsApp and transition to smart cadence",
            }

    # 7. Smart Cadence by Days Since First Contact (§4)
    day_num = max(1, days_since_first_contact or 1)

    if day_num <= 3:
        # Days 1–3: Once a day, rotating morning / afternoon / evening
        slot_name, hr, mn = ROTATING_SLOTS_IST[(day_num - 1) % len(ROTATING_SLOTS_IST)]
        days_ahead = 1 if calls_today >= 1 else 1
        next_dt = (now + timedelta(days=days_ahead)).replace(hour=hr, minute=mn, second=0, microsecond=0)
        return {
            "should_followup": True,
            "stage": "days_1_to_3",
            "channel": "ai_call",
            "slot_name": slot_name,
            "next_action_at": next_dt.isoformat(),
            "reason": f"Smart cadence Days 1–3: daily rotating {slot_name} call",
        }

    if day_num <= 10:
        # Days 4–10: Every 2 days, at the hour they picked up before; WhatsApp nudge if 2 misses in a row
        pickup_hr = preferred_pickup_hour if (preferred_pickup_hour and 9 <= preferred_pickup_hour < 21) else 11
        next_dt = (now + timedelta(days=2)).replace(hour=pickup_hr, minute=0, second=0, microsecond=0)
        channel = "ai_call_with_whatsapp_nudge" if consecutive_misses >= 2 else "ai_call"
        return {
            "should_followup": True,
            "stage": "days_4_to_10",
            "channel": channel,
            "next_action_at": next_dt.isoformat(),
            "reason": "Smart cadence Days 4–10: every 2 days at preferred pickup hour",
        }

    if day_num <= 30:
        # Days 11–30: Twice a week (every 3 days)
        next_dt = (now + timedelta(days=3)).replace(hour=11, minute=30, second=0, microsecond=0)
        return {
            "should_followup": True,
            "stage": "days_11_to_30",
            "channel": "ai_call_or_whatsapp",
            "next_action_at": next_dt.isoformat(),
            "reason": "Smart cadence Days 11–30: twice a week",
        }

    # Days 31–60: Weekly, WhatsApp first, call if they reply
    next_dt = (now + timedelta(days=7)).replace(hour=11, minute=0, second=0, microsecond=0)
    return {
        "should_followup": True,
        "stage": "days_31_to_60",
        "channel": "whatsapp_first",
        "next_action_at": next_dt.isoformat(),
        "reason": "Smart cadence Days 31–60: weekly WhatsApp first, call if they reply",
    }


def build_caller_memory_context(lead_info: Optional[Dict[str, Any]], recent_calls: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Builds the Caller Memory block (§4) injected into the AI sales prompt so
    follow-up calls remember the last conversation, budget, timeline, and objections.
    """
    if not lead_info and not recent_calls:
        return ""

    lead_info = lead_info or {}
    last_call = recent_calls[0] if recent_calls else {}

    summary = last_call.get("summary") or lead_info.get("last_call_summary") or ""
    budget = last_call.get("extracted_budget") or lead_info.get("budget") or ""
    timeline = last_call.get("extracted_timeline") or lead_info.get("timeline") or ""
    requirements = last_call.get("extracted_requirements") or lead_info.get("service_needed") or ""
    objections = last_call.get("objections_raised") or lead_info.get("objections_noted") or ""
    outcome_label = last_call.get("outcome_label") or lead_info.get("outcome_label") or ""
    outcome_reason = last_call.get("outcome_reason") or lead_info.get("outcome_reason") or ""

    if not any([summary, outcome_label, objections]):
        return ""

    lines = [
        "\nCALLER MEMORY (PREVIOUS CONVERSATION CONTEXT — USE NATURALLY IN FOLLOW-UP):"
    ]
    if summary:
        lines.append(f"- Last Conversation Summary: {summary}")
    if outcome_label:
        lines.append(f"- Previous Call Outcome: {outcome_label}" + (f" ({outcome_reason})" if outcome_reason else ""))
    if requirements:
        lines.append(f"- Discussed Requirement: {requirements}")
    if budget and budget not in {"Flexible", "Not specified"}:
        lines.append(f"- Discussed Budget: {budget}")
    if timeline and timeline not in {"Immediate", "Not specified"}:
        lines.append(f"- Discussed Timeline: {timeline}")
    if objections and objections != "None":
        lines.append(f"- Previous Objection / Hesitation: {objections}")
    lines.append(
        "INSTRUCTION: Reference our previous conversation naturally (e.g., 'Last time we spoke you mentioned...') "
        "instead of starting from scratch as a cold call.\n"
    )
    return "\n".join(lines)
