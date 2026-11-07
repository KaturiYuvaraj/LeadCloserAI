"""
Calling rules: checked before every outbound dial.

Returns one of:
  - allowed
  - blocked   (never call: opted out, no consent, invalid number, account not approved)
  - deferred  (not now: outside calling hours/days, called recently, weekly limit,
               low credit). `next_allowed_at` says when to try again.

Times are stored in UTC; calling windows are in India time (IST, UTC+5:30, no DST).
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Account, Call, CreditLedger, Lead, OptOut

IST = timezone(timedelta(hours=5, minutes=30))

# Legal window for business calls in India; account settings can only narrow it.
LEGAL_START = time(9, 0)
LEGAL_END = time(21, 0)

WEEKLY_CALL_LIMIT = int(os.getenv("DIALER_WEEKLY_CALL_LIMIT", "4"))
MIN_CREDIT = float(os.getenv("DIALER_MIN_CREDIT", "0"))  # 0 = credit check off until billing is live
REQUIRE_CONSENT = os.getenv("DIALER_REQUIRE_CONSENT", "true").lower() != "false"

# Lead sources where the person contacted us themselves (consent is implied)
SELF_INITIATED_SOURCES = {"webform", "webhook", "meta", "google", "inbound", "api", "manual"}

E164 = re.compile(r"^\+\d{10,15}$")
INDIAN_MOBILE_OR_LANDLINE = re.compile(r"^\+91[1-9]\d{9}$")


@dataclass
class RuleResult:
    status: str  # allowed | blocked | deferred
    reason: str = ""
    next_allowed_at: Optional[datetime] = None

    @property
    def allowed(self) -> bool:
        return self.status == "allowed"


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def db_time(session: Session, dt: datetime) -> datetime:
    """Datetime in the form the database compares correctly: naive UTC for SQLite, aware for PostgreSQL."""
    dt = as_utc(dt)
    return dt.replace(tzinfo=None) if session.get_bind().dialect.name == "sqlite" else dt


def calling_window(account: Account) -> tuple[time, time, list[int]]:
    """Account window clamped to the legal 9 AM–9 PM; days are Monday=0 … Sunday=6."""
    start = max(account.calling_start or LEGAL_START, LEGAL_START)
    end = min(account.calling_end or LEGAL_END, LEGAL_END)
    days = account.calling_days if isinstance(account.calling_days, list) and account.calling_days else list(range(7))
    return start, end, [int(d) for d in days]


def next_window_start(now_utc: datetime, account: Account) -> datetime:
    """The next moment (UTC) inside the account's calling window."""
    start, end, days = calling_window(account)
    local = now_utc.astimezone(IST)
    for offset in range(0, 8):
        day = (local + timedelta(days=offset)).date()
        if day.weekday() not in days:
            continue
        window_start = datetime.combine(day, start, tzinfo=IST)
        window_end = datetime.combine(day, end, tzinfo=IST)
        if offset == 0 and window_start <= local < window_end:
            return now_utc
        if window_start > local:
            return window_start.astimezone(timezone.utc)
    return (local + timedelta(days=1)).astimezone(timezone.utc)


def in_calling_window(now_utc: datetime, account: Account) -> bool:
    return next_window_start(now_utc, account) == now_utc


def is_dialable_number(phone: str) -> bool:
    phone = (phone or "").strip()
    if phone.startswith("+91"):
        return bool(INDIAN_MOBILE_OR_LANDLINE.match(phone))
    return bool(E164.match(phone))


def credit_balance(session: Session, account_id: int) -> float:
    total = session.query(func.coalesce(func.sum(CreditLedger.delta), 0)).filter(
        CreditLedger.account_id == account_id
    ).scalar()
    return float(total or 0)


def check_can_call(session: Session, account: Account, lead: Lead, now_utc: datetime,
                   is_retry: bool = False) -> RuleResult:
    """Run every rule in order; the first one that fails decides."""
    # Never call
    if not account.calling_approved:
        return RuleResult("blocked", "account_not_approved")
    if lead.opt_out:
        return RuleResult("blocked", "opted_out")
    opted_out = session.query(OptOut.id).filter(
        OptOut.account_id == account.id, OptOut.phone_e164 == lead.phone_e164
    ).first()
    if opted_out:
        return RuleResult("blocked", "opted_out")
    if not is_dialable_number(lead.phone_e164):
        return RuleResult("blocked", "invalid_number")
    if REQUIRE_CONSENT and not lead.consent_source and (lead.source or "").lower() not in SELF_INITIATED_SOURCES:
        return RuleResult("blocked", "no_consent")

    # Not now (only enforce calling hours for automatic batch campaigns, not manual dials or retries)
    if not is_retry:
        window_start = next_window_start(now_utc, account)
        if window_start != now_utc:
            return RuleResult("deferred", "outside_calling_hours", window_start)

    if not is_retry and account.recent_call_hours:
        last_call = session.query(func.max(Call.created_at)).filter(Call.lead_id == lead.id).scalar()
        last_call = as_utc(last_call)
        if last_call and now_utc - last_call < timedelta(hours=account.recent_call_hours):
            later = last_call + timedelta(hours=account.recent_call_hours)
            return RuleResult("deferred", "called_recently", next_window_start(later, account))

    week_ago = now_utc - timedelta(days=7)
    calls_this_week = session.query(func.count(Call.id)).filter(
        Call.lead_id == lead.id, Call.created_at >= db_time(session, week_ago)
    ).scalar() or 0
    if calls_this_week >= WEEKLY_CALL_LIMIT:
        return RuleResult("deferred", "weekly_limit", next_window_start(now_utc + timedelta(days=2), account))

    if MIN_CREDIT > 0 and credit_balance(session, account.id) < MIN_CREDIT:
        return RuleResult("deferred", "low_credit", now_utc + timedelta(hours=1))

    return RuleResult("allowed")
