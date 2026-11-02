from datetime import time
from sqlalchemy import Column, Integer, String, Time, Boolean, Numeric, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    default_language = Column(String(16), nullable=False, default="te-IN")
    calling_start = Column(Time, nullable=True, default=time(9, 0))
    calling_end = Column(Time, nullable=True, default=time(19, 0))
    calling_days = Column(JSON, nullable=True, default=list(range(7)))
    max_call_seconds = Column(Integer, nullable=False, default=600)
    recent_call_hours = Column(Integer, nullable=False, default=24)
    calling_approved = Column(Boolean, nullable=False, default=False)
    rate_per_min = Column(Numeric(10, 2), nullable=False, default=5.00)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
