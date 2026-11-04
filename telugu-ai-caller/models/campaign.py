from typing import Any
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    name: Any = Column(String(255), nullable=False)
    description: Any = Column(Text, nullable=True)
    employee_id: Any = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_ids_json: Any = Column(Text, nullable=False, default="[]")
    mode: Any = Column(String(32), nullable=False, default="telephony")
    status: Any = Column(String(32), nullable=False, default="draft")
    total_leads: Any = Column(Integer, nullable=False, default=0)
    completed_leads: Any = Column(Integer, nullable=False, default=0)
    max_concurrency: Any = Column(Integer, nullable=False, default=3)
    retry_attempts: Any = Column(Integer, nullable=False, default=2)
    results_json: Any = Column(Text, nullable=False, default="{}")
    logs_json: Any = Column(Text, nullable=False, default="[]")
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
