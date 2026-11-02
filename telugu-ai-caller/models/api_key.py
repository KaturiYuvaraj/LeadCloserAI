from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_name = Column(String(128), nullable=False)
    user_email = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    plan_tier = Column(String(64), nullable=False, default="Business Growth")
    credits_inr = Column(Float, nullable=False, default=2500.0)
    rate_per_min = Column(Float, nullable=False, default=5.0)
    total_calls = Column(Integer, nullable=False, default=0)
    total_minutes = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
