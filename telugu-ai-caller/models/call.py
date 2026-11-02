from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    number_id = Column(Integer, ForeignKey("numbers.id", ondelete="SET NULL"), nullable=True, index=True)
    direction = Column(String(16), nullable=False, default="out")  # out | in
    channel = Column(String(32), nullable=False, default="manual")  # manual | instant | inbound | retry | test
    state = Column(String(32), nullable=False, default="completed")
    provider_call_sid = Column(String(128), nullable=True, index=True)
    queued_at = Column(DateTime(timezone=True), nullable=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    talk_seconds = Column(Integer, nullable=False, default=0)
    billed_blocks = Column(Integer, nullable=False, default=0)
    credits = Column(Numeric(10, 2), nullable=False, default=0.00)
    outcome = Column(String(64), nullable=True)
    sentiment = Column(String(32), nullable=False, default="neutral")
    ended_by = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    objections_raised = Column(Text, nullable=True)
    extracted_requirements = Column(Text, nullable=True)
    captured = Column(JSON, nullable=True)
    transcript = Column(JSON, nullable=True)
    recording_url = Column(Text, nullable=True)
    latency_avg_ms = Column(Numeric(10, 2), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
