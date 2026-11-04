from typing import Any
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ProviderUsageLog(Base):
    __tablename__ = "provider_usage_logs"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    provider_name: Any = Column(String(64), nullable=False)
    operation: Any = Column(String(64), nullable=False)
    credits_used: Any = Column(Float, nullable=False, default=1.0)
    details: Any = Column(Text, nullable=True)
    timestamp: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
