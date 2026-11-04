from typing import Any
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    key_name: Any = Column(String(128), nullable=False)
    user_email: Any = Column(String(255), nullable=False)
    company_name: Any = Column(String(255), nullable=True)
    api_key: Any = Column(String(255), unique=True, nullable=False, index=True)
    plan_tier: Any = Column(String(64), nullable=False, default="Business Growth")
    credits_inr: Any = Column(Float, nullable=False, default=2500.0)
    rate_per_min: Any = Column(Float, nullable=False, default=5.0)
    total_calls: Any = Column(Integer, nullable=False, default=0)
    total_minutes: Any = Column(Float, nullable=False, default=0.0)
    status: Any = Column(String(32), nullable=False, default="active")
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
