from typing import Any
from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Call(Base):
    __tablename__ = "calls"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Any = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id: Any = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    number_id: Any = Column(Integer, ForeignKey("numbers.id", ondelete="SET NULL"), nullable=True, index=True)
    direction: Any = Column(String(16), nullable=False, default="out")  # out | in
    channel: Any = Column(String(32), nullable=False, default="manual")  # manual | instant | inbound | retry | test
    state: Any = Column(String(32), nullable=False, default="completed")
    provider_call_sid: Any = Column(String(128), nullable=True, index=True)
    queued_at: Any = Column(DateTime(timezone=True), nullable=True)
    answered_at: Any = Column(DateTime(timezone=True), nullable=True)
    ended_at: Any = Column(DateTime(timezone=True), nullable=True)
    talk_seconds: Any = Column(Integer, nullable=False, default=0)
    billed_blocks: Any = Column(Integer, nullable=False, default=0)
    credits: Any = Column(Numeric(10, 2), nullable=False, default=0.00)
    outcome: Any = Column(String(64), nullable=True)
    sentiment: Any = Column(String(32), nullable=False, default="neutral")
    ended_by: Any = Column(String(32), nullable=True)
    summary: Any = Column(Text, nullable=True)
    action_items: Any = Column(Text, nullable=True)
    objections_raised: Any = Column(Text, nullable=True)
    extracted_requirements: Any = Column(Text, nullable=True)
    captured: Any = Column(JSON, nullable=True)
    transcript: Any = Column(JSON, nullable=True)
    recording_url: Any = Column(Text, nullable=True)
    latency_avg_ms: Any = Column(Numeric(10, 2), nullable=True)
    error: Any = Column(Text, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
