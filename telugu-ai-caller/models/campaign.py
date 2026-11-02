from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_ids_json = Column(Text, nullable=False, default="[]")
    mode = Column(String(32), nullable=False, default="telephony")
    status = Column(String(32), nullable=False, default="draft")
    total_leads = Column(Integer, nullable=False, default=0)
    completed_leads = Column(Integer, nullable=False, default=0)
    max_concurrency = Column(Integer, nullable=False, default=3)
    retry_attempts = Column(Integer, nullable=False, default=2)
    results_json = Column(Text, nullable=False, default="{}")
    logs_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
