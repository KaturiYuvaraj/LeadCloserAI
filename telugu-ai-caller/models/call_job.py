from typing import Any
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class CallJob(Base):
    """
    One outbound call to be made by the dialer (voice_agent/dialer.py).

    Life cycle: queued → dialing → in_progress → completed
                queued → scheduled (outside calling hours etc.) → queued …
                dialing → retry_scheduled (no answer / busy) → … → not_reachable
                queued → blocked (opted out, no consent, invalid number)
                any open state → cancelled (campaign stopped)
    """
    __tablename__ = "call_jobs"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Any = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Any = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    phone_e164: Any = Column(String(32), nullable=False)
    language: Any = Column(String(16), nullable=True)
    provider: Any = Column(String(32), nullable=False, default="fake")  # vobiz | exotel | fake
    state: Any = Column(String(32), nullable=False, default="queued", index=True)
    priority: Any = Column(Integer, nullable=False, default=5)  # lower = sooner (0 = call now)
    attempt: Any = Column(Integer, nullable=False, default=0)
    max_attempts: Any = Column(Integer, nullable=False, default=3)
    next_attempt_at: Any = Column(DateTime(timezone=True), nullable=True, index=True)
    provider_call_id: Any = Column(String(128), nullable=True, index=True)
    call_id: Any = Column(Integer, ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)
    last_disposition: Any = Column(String(64), nullable=True)   # answered | no_answer | busy | failed | <deal outcome>
    block_reason: Any = Column(String(255), nullable=True)
    last_error: Any = Column(Text, nullable=True)
    dialed_at: Any = Column(DateTime(timezone=True), nullable=True)
    answered_at: Any = Column(DateTime(timezone=True), nullable=True)
    finished_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
