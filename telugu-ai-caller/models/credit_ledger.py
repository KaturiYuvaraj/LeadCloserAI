from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, Index, text
from sqlalchemy.sql import func
from core.db import Base


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    delta = Column(Numeric(10, 2), nullable=False)
    reason = Column(String(32), nullable=False)  # admin_topup | call | adjust | refund
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="SET NULL"), nullable=True, index=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "uq_credit_ledger_call_id",
            "call_id",
            unique=True,
            postgresql_where=text("reason = 'call'")
        ),
    )
