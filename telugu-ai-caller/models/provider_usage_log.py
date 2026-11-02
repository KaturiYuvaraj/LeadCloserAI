from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ProviderUsageLog(Base):
    __tablename__ = "provider_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(64), nullable=False)
    operation = Column(String(64), nullable=False)
    credits_used = Column(Float, nullable=False, default=1.0)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
