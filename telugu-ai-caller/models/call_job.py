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

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    phone_e164 = Column(String(32), nullable=False)
    language = Column(String(16), nullable=True)
    provider = Column(String(32), nullable=False, default="fake")  # vobiz | exotel | fake
    state = Column(String(32), nullable=False, default="queued", index=True)
    priority = Column(Integer, nullable=False, default=5)  # lower = sooner (0 = call now)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    provider_call_id = Column(String(128), nullable=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)
    last_disposition = Column(String(64), nullable=True)   # answered | no_answer | busy | failed | <deal outcome>
    block_reason = Column(String(255), nullable=True)
    last_error = Column(Text, nullable=True)
    dialed_at = Column(DateTime(timezone=True), nullable=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
