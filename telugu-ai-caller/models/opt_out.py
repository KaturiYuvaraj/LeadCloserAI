from typing import Any
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from core.db import Base


class OptOut(Base):
    __tablename__ = "opt_outs"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_e164: Any = Column(String(32), nullable=False, index=True)
    reason: Any = Column(String(255), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "phone_e164", name="uq_opt_outs_account_phone"),
    )
