from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from core.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    job_type = Column(String(32), nullable=False, default="instant")  # instant | inbound | bulk
    language = Column(String(16), nullable=False, default="te-IN")
    voice = Column(String(64), nullable=False, default="kavitha_te_conversation")
    tier = Column(String(32), nullable=False, default="standard")
    greeting = Column(Text, nullable=False)
    script_steps = Column(JSON, nullable=True)
    system_prompt = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="draft")  # draft | testing | live
    number_id = Column(Integer, ForeignKey("numbers.id", ondelete="SET NULL"), nullable=True, index=True)
    webhook_slug = Column(String(128), unique=True, nullable=True, index=True)
    webhook_secret_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
