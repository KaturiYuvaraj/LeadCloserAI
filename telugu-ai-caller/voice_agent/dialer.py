"""
Outbound call queue (Phase 0).

Leads are queued as CallJob rows (restart-safe). A background loop runs every second:
  1. expires calls the provider never reported back on,
  2. takes due jobs (call-now first, then by queue order) while lines are free,
  3. runs the calling rules (voice_agent/rules.py) on each:
       blocked  → job.state = blocked (reason kept, never dialled)
       deferred → job.state = scheduled until the next allowed time
       allowed  → dial through the configured provider (voice_agent/outbound.py)
  4. provider callbacks and the voice engine move jobs on:
       answered → in_progress → completed (call saved by the engine)
       no answer / busy / failed → retry_scheduled (+2 h, next day at another time) → not_reachable
  5. follow-ups (voice_agent/followups.py): after a conversation, or once a lead stays
     unreachable, the next call is queued on the smart cadence until the lead decides

All database work runs in a worker thread so live calls' audio is never blocked.
"""

import asyncio
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

from sqlalchemy import func

from core.db import SessionLocal
from database import save_call_record
from models import Account, Call, CallJob, Lead
from voice_agent import credits, followups
from voice_agent.outbound import DialError, DialRequest, get_dialer
from voice_agent.rules import IST, as_utc, check_can_call, db_time, next_window_start

OPEN_STATES = ("queued", "scheduled", "retry_scheduled", "dialing", "in_progress")
WAITING_STATES = ("queued", "scheduled", "retry_scheduled")
ACTIVE_STATES = ("dialing", "in_progress")

DISPOSITIONS = {
    "no-answer": "no_answer", "no_answer": "no_answer", "noanswer": "no_answer", "timeout": "no_answer",
    "busy": "busy", "user_busy": "busy",
    "failed": "failed", "canceled": "failed", "cancelled": "failed", "rejected": "failed",
    "completed": "completed", "answered": "completed",
}

# Answered by a machine or nobody spoke: the engine ends the call and it is retried like no-answer
RETRY_ENGINE_OUTCOMES = {"voicemail", "ivr", "unreachable", "no_response"}
# Our side failed (Sarvam credits finished / key rejected): the lead goes back in the queue,
# and the attempt does not count against it
SERVICE_FAILED = "service_unavailable"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallQueue:
    def __init__(self):
        self.dialer = get_dialer()
        self.max_lines = int(os.getenv("DIALER_MAX_LINES", "3"))
        self.dial_timeout = timedelta(seconds=int(os.getenv("DIALER_DIAL_TIMEOUT_SECONDS", "120")))
        self.paused = False
        self.run_started_at: Optional[datetime] = None
        self.events: deque = deque(maxlen=200)
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Call queue started · provider {self.dialer.name} · {self.max_lines} lines")

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    def log(self, message: str, level: str = "info", lead_id: Optional[int] = None):
        self.events.append({
            "time": utcnow().astimezone(IST).strftime("%H:%M:%S"),
            "message": message, "level": level, "lead_id": lead_id,
        })
        logger.info(f"[DIALER] {message}")

    async def _loop(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Call queue tick failed: {e}")
            await asyncio.sleep(1)

    # ------------------------------------------------------------------ enqueue
    def enqueue(self, lead_ids: Iterable[int], campaign_id: Optional[int] = None, priority: int = 5,
                consent_confirmed: bool = False, language: Optional[str] = None,
                max_attempts: int = 3, consent_by: Optional[str] = None) -> Dict[str, int]:
        """Queue leads for calling. Leads that already have an open job are skipped."""
        counts = {"queued": 0, "already_queued": 0, "not_found": 0}
        now = utcnow()

        def consent_label() -> str:
            stamp = f"{now.astimezone(IST):%Y-%m-%d %H:%M} IST"
            return f"confirmed_by {consent_by} {stamp}" if consent_by else f"campaign_confirmed {stamp}"
        session = SessionLocal()
        try:
            for lead_id in lead_ids:
                lead = session.get(Lead, int(lead_id))
                if not lead:
                    counts["not_found"] += 1
                    continue
                open_jobs = session.query(CallJob).filter(
                    CallJob.lead_id == lead.id, CallJob.state.in_(OPEN_STATES)
                ).all()
                if open_jobs:
                    if priority == 0:
                        # On-demand manual "Call Now": reset open job(s) to dial immediately
                        reset = 0
                        for oj in open_jobs:
                            if oj.state in ACTIVE_STATES:
                                continue  # Already on the phone right now
                            reset += 1
                            oj.state = "queued"
                            oj.priority = 0
                            oj.next_attempt_at = db_time(session, now)
                            oj.block_reason = None
                            if language:
                                oj.language = language
                            if consent_confirmed and not lead.consent_source:
                                lead.consent_source = consent_label()
                        counts["queued" if reset else "already_queued"] += 1
                        continue
                    else:
                        counts["already_queued"] += 1
                        continue
                if consent_confirmed and not lead.consent_source:
                    lead.consent_source = consent_label()
                session.add(CallJob(
                    account_id=lead.account_id, lead_id=lead.id, campaign_id=campaign_id,
                    phone_e164=lead.phone_e164, language=language, provider=self.dialer.name,
                    state="queued", priority=priority, max_attempts=max_attempts,
                    next_attempt_at=db_time(session, now),
                ))
                counts["queued"] += 1
            session.commit()
        finally:
            session.close()
        if counts["queued"]:
            if self.run_started_at is None or not self._has_open_jobs():
                self.run_started_at = now
            self.log(f"Queued {counts['queued']} lead(s) for calling"
                     + (f" · {counts['already_queued']} already in queue" if counts["already_queued"] else ""))
        return counts

    def preview_call(self, lead_id: int, consent_confirmed: bool = False) -> Dict[str, Any]:
        """
        What the calling rules say about a person pressing "Call now" on this lead right now.
        Nothing is saved. status: allowed | blocked | deferred | not_found (+ reason, next_allowed_at,
        and how long ago the lead was last called).
        """
        session = SessionLocal()
        try:
            lead = session.get(Lead, lead_id)
            if lead is None:
                return {"status": "not_found"}
            account = session.get(Account, lead.account_id)
            now = utcnow()
            last_call = as_utc(session.query(func.max(Call.created_at)).filter(Call.lead_id == lead.id).scalar())
            session.expunge(lead)  # the consent assumption below must never be written
            if consent_confirmed and not lead.consent_source:
                lead.consent_source = "confirmed_in_dashboard"
            result = check_can_call(session, account, lead, now, is_retry=True, manual=True)
            out: Dict[str, Any] = {
                "status": result.status, "reason": result.reason,
                "last_called_hours_ago": round((now - last_call).total_seconds() / 3600, 1) if last_call else None,
                "outside_calling_hours": next_window_start(now, account) != now,
            }
            if result.next_allowed_at:
                out["next_allowed_at"] = as_utc(result.next_allowed_at).astimezone(IST).isoformat()
            return out
        finally:
            session.close()

    def open_job_id(self, lead_id: int) -> Optional[int]:
        session = SessionLocal()
        try:
            job = session.query(CallJob).filter(
                CallJob.lead_id == lead_id, CallJob.state.in_(OPEN_STATES)
            ).order_by(CallJob.id.desc()).first()
            return job.id if job else None
        finally:
            session.close()

    def _has_open_jobs(self) -> bool:
        session = SessionLocal()
        try:
            return session.query(CallJob.id).filter(CallJob.state.in_(OPEN_STATES)).first() is not None
        finally:
            session.close()

    # ------------------------------------------------------------------ the loop
    async def tick(self):
        await asyncio.to_thread(self._expire_stale_dials)
        if self.paused:
            return
        if credits.blocked():
            if credits.probe_due() and not await credits.probe():
                return
            if credits.blocked():
                return
        to_dial = await asyncio.to_thread(self._claim_due_jobs)
        for job in to_dial:
            await self._dial(job)

    def _expire_stale_dials(self):
        """A dial with no answer and no provider callback for too long counts as not answered."""
        session = SessionLocal()
        try:
            cutoff = db_time(session, utcnow() - self.dial_timeout)
            stale = session.query(CallJob).filter(
                CallJob.state == "dialing", CallJob.dialed_at < cutoff
            ).all()
            for job in stale:
                self._schedule_retry(session, job, "no_answer", "no callback from provider")
            session.commit()
        finally:
            session.close()

    def _claim_due_jobs(self) -> List[Dict[str, Any]]:
        session = SessionLocal()
        claimed: List[Dict[str, Any]] = []
        try:
            now = utcnow()
            active = session.query(CallJob.id).filter(CallJob.state.in_(ACTIVE_STATES)).count()
            free_lines = self.max_lines - active
            if free_lines <= 0:
                return []

            due = session.query(CallJob).filter(
                CallJob.state.in_(WAITING_STATES), CallJob.next_attempt_at <= db_time(session, now)
            ).order_by(CallJob.priority, CallJob.next_attempt_at, CallJob.id).limit(free_lines * 5).all()

            accounts: Dict[int, Account] = {}
            for job in due:
                if len(claimed) >= free_lines:
                    break
                lead = session.get(Lead, job.lead_id)
                if lead is None:
                    job.state, job.block_reason = "cancelled", "lead_deleted"
                    continue
                account = accounts.get(job.account_id) or session.get(Account, job.account_id)
                accounts[job.account_id] = account

                # a callback the customer asked for, or a follow-up already spaced out by the cadence,
                # is not held back by "called recently"
                is_retry = job.attempt > 0 or job.priority == 0 or job.last_disposition in ("callback_requested", SERVICE_FAILED,
                                                                       followups.FOLLOWUP_DISPOSITION)
                result = check_can_call(session, account, lead, now, is_retry=is_retry, manual=job.priority == 0)
                if result.status == "blocked":
                    job.state, job.block_reason = "blocked", result.reason
                    self.log(f"⛔ Not calling {lead.name}: {result.reason.replace('_', ' ')}", "warning", lead.id)
                    continue
                if result.status == "deferred":
                    if job.block_reason != result.reason:
                        when = result.next_allowed_at.astimezone(IST).strftime("%d %b %H:%M")
                        self.log(f"🕒 {lead.name}: {result.reason.replace('_', ' ')} · will call at {when} IST",
                                 "info", lead.id)
                    job.state, job.block_reason = "scheduled", result.reason
                    job.next_attempt_at = db_time(session, result.next_allowed_at)
                    continue

                job.state, job.block_reason = "dialing", None
                job.attempt += 1
                job.provider = self.dialer.name
                job.dialed_at = db_time(session, now)
                claimed.append({
                    "id": job.id, "lead_id": lead.id, "lead_name": lead.name,
                    "phone": lead.phone_e164, "attempt": job.attempt,
                    "language": job.language or (lead.variables or {}).get("preferred_language"),
                    "max_call_seconds": account.max_call_seconds or 600,
                })
            session.commit()
        finally:
            session.close()
        return claimed

    async def _dial(self, job: Dict[str, Any]):
        req = DialRequest(job_id=job["id"], lead_id=job["lead_id"], to_number=job["phone"],
                          language=job["language"], max_call_seconds=job["max_call_seconds"])
        try:
            provider_call_id = await self.dialer.dial(req)
        except Exception as e:  # DialError or network failure
            self.log(f"⚠️ Could not dial {job['lead_name']}: {e}", "error", job["lead_id"])
            await asyncio.to_thread(self._update_job, job["id"], retry=("failed", str(e)))
            return
        await asyncio.to_thread(self._update_job, job["id"], provider_call_id=provider_call_id)
        self.log(f"📞 Dialing {job['lead_name']} ({job['phone']}) · attempt {job['attempt']} · {self.dialer.name}",
                 "info", job["lead_id"])

    # ------------------------------------------------------------------ job updates
    def _update_job(self, job_id: int, provider_call_id: Optional[str] = None, retry: Optional[tuple] = None):
        session = SessionLocal()
        try:
            job = session.get(CallJob, job_id)
            if not job:
                return
            if provider_call_id:
                job.provider_call_id = provider_call_id
            if retry:
                self._schedule_retry(session, job, retry[0], retry[1])
            session.commit()
        finally:
            session.close()

    def _schedule_retry(self, session, job: CallJob, disposition: str, error: Optional[str] = None):
        job.last_disposition = disposition
        job.last_error = error
        job.finished_at = db_time(session, utcnow())
        lead = session.get(Lead, job.lead_id)
        name = lead.name if lead else f"lead {job.lead_id}"
        if job.attempt >= job.max_attempts:
            job.state = "not_reachable"
            if lead:
                lead.last_outcome = "not_reachable"
            self.log(f"📵 {name}: not reachable after {job.attempt} attempts", "warning", job.lead_id)
            self._log_followup(name, job.lead_id, followups.after_unreachable(session, job, utcnow()))
            return
        retry_at = followups.retry_time(job.attempt, utcnow())
        job.state = "retry_scheduled"
        job.next_attempt_at = db_time(session, retry_at)
        self.log(f"🔁 {name}: {disposition.replace('_', ' ')} · retry at "
                 f"{retry_at.astimezone(IST):%d %b %H:%M} IST", "info", job.lead_id)

    def _log_followup(self, name: str, lead_id: int, next_call: Optional[datetime]):
        if next_call:
            self.log(f"📅 {name}: follow-up call at {next_call.astimezone(IST):%d %b %H:%M} IST", "info", lead_id)

    # ------------------------------------------------------------------ callbacks
    def on_answered(self, job_id: int):
        """Provider fetched our Answer URL: the lead picked up."""
        session = SessionLocal()
        try:
            job = session.get(CallJob, job_id)
            if job and job.state in ("dialing", "queued", "retry_scheduled", "scheduled"):
                job.state = "in_progress"
                job.answered_at = db_time(session, utcnow())
                job.last_disposition = "answered"
                session.commit()
                lead = session.get(Lead, job.lead_id)
                self.log(f"🟢 {lead.name if lead else job.lead_id} answered", "success", job.lead_id)
        finally:
            session.close()

    def on_call_saved(self, job_id: int, call_id: Optional[int], outcome: str):
        """The voice engine finished the conversation and saved the call."""
        session = SessionLocal()
        try:
            job = session.get(CallJob, job_id)
            if not job:
                return
            if outcome == SERVICE_FAILED:
                job.call_id = call_id
                job.state, job.attempt = "queued", max(0, job.attempt - 1)
                job.last_disposition, job.block_reason = SERVICE_FAILED, (credits.blocked() or {}).get("reason")
                session.commit()
                self.log("⛔ Call ended: Sarvam unavailable · lead back in the queue", "error", job.lead_id)
                return
            if outcome in RETRY_ENGINE_OUTCOMES:
                job.call_id = call_id
                self._schedule_retry(session, job, outcome)
                session.commit()
                return
            job.state = "completed"
            job.call_id = call_id
            job.last_disposition = outcome or "completed"
            job.finished_at = db_time(session, utcnow())
            next_call = followups.after_conversation(session, job, outcome, utcnow())
            session.commit()
            lead = session.get(Lead, job.lead_id)
            name = lead.name if lead else str(job.lead_id)
            self.log(f"✅ Call with {name} done · {(outcome or 'completed').replace('_', ' ')}",
                     "success", job.lead_id)
            self._log_followup(name, job.lead_id, next_call)
        finally:
            session.close()

    def on_provider_hangup(self, job_id: int, status: str, duration: int = 0, cause: str = ""):
        """Provider says the call ended. Only matters if it was never answered."""
        disposition = DISPOSITIONS.get((status or "").strip().lower().replace(" ", "_"), "failed")
        session = SessionLocal()
        try:
            job = session.get(CallJob, job_id)
            if not job or job.state in ("completed", "cancelled", "blocked", "not_reachable"):
                return
            if job.state == "in_progress":
                job.state = "completed"
                session.commit()
                return  # provider confirmed hangup
            if disposition == "completed" and duration > 0:
                return  # answered; the engine callback will follow
            lead = session.get(Lead, job.lead_id)
            not_connected = "failed" if disposition == "completed" else disposition
            self._schedule_retry(session, job, not_connected, cause or None)
            session.commit()
            lead_id = job.lead_id
            phone = lead.phone_e164 if lead else job.phone_e164
        finally:
            session.close()
        # Record the attempt on the lead's call history (0 s, nothing billed)
        try:
            save_call_record({
                "lead_id": lead_id, "call_type": "phone", "phone_number": phone,
                "duration_seconds": 0, "status": not_connected, "deal_stage": not_connected,
                "summary": f"Call not connected ({not_connected.replace('_', ' ')}).",
                "transcript": "[]",
            })
        except Exception as e:
            logger.warning(f"Could not record unanswered attempt: {e}")

    # ------------------------------------------------------------------ controls
    def pause(self):
        self.paused = True
        self.log("⏸ Calling paused (calls in progress continue)", "warning")

    def resume(self):
        self.paused = False
        credits.clear("resumed from the dashboard")
        self.log("▶ Calling resumed")

    def cancel_waiting(self, campaign_id: Optional[int] = None) -> int:
        session = SessionLocal()
        try:
            query = session.query(CallJob).filter(CallJob.state.in_(WAITING_STATES))
            if campaign_id is not None:
                query = query.filter(CallJob.campaign_id == campaign_id)
            jobs = query.all()
            for job in jobs:
                job.state, job.block_reason = "cancelled", "stopped_by_user"
            session.commit()
            if jobs:
                self.log(f"⏹ Stopped · {len(jobs)} waiting call(s) cancelled", "warning")
            return len(jobs)
        finally:
            session.close()

    # ------------------------------------------------------------------ status
    def status(self) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            query = session.query(CallJob)
            if self.run_started_at:
                query = query.filter(CallJob.created_at >= db_time(session, self.run_started_at - timedelta(seconds=5)))
            jobs = query.all()
            counts: Dict[str, int] = {}
            outcomes: Dict[str, int] = {}
            for job in jobs:
                counts[job.state] = counts.get(job.state, 0) + 1
                if job.state == "completed":
                    key = (job.last_disposition or "completed").lower()
                    outcomes[key] = outcomes.get(key, 0) + 1
            active = []
            for job in jobs:
                if job.state in ACTIVE_STATES:
                    lead = session.get(Lead, job.lead_id)
                    active.append({"job_id": job.id, "lead_id": job.lead_id,
                                   "name": lead.name if lead else "", "phone": job.phone_e164,
                                   "state": job.state, "attempt": job.attempt})
            next_due = [as_utc(j.next_attempt_at) for j in jobs if j.state in WAITING_STATES and j.next_attempt_at]
        finally:
            session.close()
        total = len(jobs)
        done = sum(counts.get(s, 0) for s in ("completed", "not_reachable", "blocked", "cancelled"))
        return {
            "provider": self.dialer.name,
            "max_lines": self.max_lines,
            "paused": self.paused,
            "service_block": credits.blocked(),
            "running": bool(self._task and not self._task.done()),
            "total": total,
            "finished": done,
            "counts": counts,
            "outcomes": outcomes,
            "active_calls": active,
            "next_call_at": min(next_due).astimezone(IST).isoformat() if next_due else None,
            "events": list(self.events)[-40:],
        }


call_queue = CallQueue()
