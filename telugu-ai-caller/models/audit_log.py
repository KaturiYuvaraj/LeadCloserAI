from typing import Any
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Any = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Any = Column(String(64), nullable=False)
    target: Any = Column(String(128), nullable=True)
    details: Any = Column(JSON, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
