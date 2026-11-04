from typing import Any
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from core.db import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Any = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Any = Column(String(255), nullable=False)
    phone: Any = Column(String(32), nullable=True)
    phone_e164: Any = Column(String(32), nullable=False, index=True)
    company: Any = Column(String(255), nullable=True)
    source: Any = Column(String(64), nullable=False, default="manual")  # manual | csv | webhook | inbound
    variables: Any = Column(JSON, nullable=True)
    consent_source: Any = Column(String(255), nullable=True)
    opt_out: Any = Column(Boolean, nullable=False, default=False)
    last_outcome: Any = Column(String(64), nullable=True)
    is_hot: Any = Column(Boolean, nullable=False, default=False)
    callback_at: Any = Column(DateTime(timezone=True), nullable=True)
    notes: Any = Column(Text, nullable=True)
    last_call_summary: Any = Column(Text, nullable=True)
    action_items: Any = Column(Text, nullable=True)
    objections_noted: Any = Column(Text, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "phone_e164", name="uq_leads_account_phone"),
    )
