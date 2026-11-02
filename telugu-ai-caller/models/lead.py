from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from core.db import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    phone_e164 = Column(String(32), nullable=False, index=True)
    source = Column(String(64), nullable=False, default="manual")  # manual | csv | webhook | inbound
    variables = Column(JSON, nullable=True)
    consent_source = Column(String(255), nullable=True)
    opt_out = Column(Boolean, nullable=False, default=False)
    last_outcome = Column(String(64), nullable=True)
    is_hot = Column(Boolean, nullable=False, default=False)
    callback_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    last_call_summary = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    objections_noted = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "phone_e164", name="uq_leads_account_phone"),
    )
