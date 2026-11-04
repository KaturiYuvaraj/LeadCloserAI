from typing import Any
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Any = Column(String(255), nullable=False)
    job_type: Any = Column(String(32), nullable=False, default="instant")  # instant | inbound | bulk
    language: Any = Column(String(16), nullable=False, default="te-IN")
    voice: Any = Column(String(64), nullable=False, default="kavitha_te_conversation")
    tier: Any = Column(String(32), nullable=False, default="standard")
    greeting: Any = Column(Text, nullable=False)
    script_steps: Any = Column(JSON, nullable=True)
    system_prompt: Any = Column(Text, nullable=False)
    variables: Any = Column(JSON, nullable=True)
    status: Any = Column(String(32), nullable=False, default="draft")  # draft | testing | live
    number_id: Any = Column(Integer, ForeignKey("numbers.id", ondelete="SET NULL"), nullable=True, index=True)
    webhook_slug: Any = Column(String(128), unique=True, nullable=True, index=True)
    webhook_secret_hash: Any = Column(String(255), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
