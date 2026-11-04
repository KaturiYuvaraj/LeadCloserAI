from datetime import time
from typing import Any
from sqlalchemy import Column, Integer, String, Time, Boolean, Numeric, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    name: Any = Column(String(255), nullable=False)
    default_language: Any = Column(String(16), nullable=False, default="te-IN")
    calling_start: Any = Column(Time, nullable=True, default=time(9, 0))
    calling_end: Any = Column(Time, nullable=True, default=time(19, 0))
    calling_days: Any = Column(JSON, nullable=True, default=list(range(7)))
    max_call_seconds: Any = Column(Integer, nullable=False, default=600)
    recent_call_hours: Any = Column(Integer, nullable=False, default=24)
    calling_approved: Any = Column(Boolean, nullable=False, default=False)
    rate_per_min: Any = Column(Numeric(10, 2), nullable=False, default=5.00)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
