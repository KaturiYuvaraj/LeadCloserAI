from typing import Any
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ProviderSetting(Base):
    __tablename__ = "provider_settings"

    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    provider_type: Any = Column(String(64), primary_key=True)
    provider_name: Any = Column(String(64), primary_key=True)
    is_enabled: Any = Column(Boolean, nullable=False, default=True)
    is_configured: Any = Column(Boolean, nullable=False, default=False)
    config_json: Any = Column(Text, nullable=False, default="{}")
    last_tested_at: Any = Column(DateTime(timezone=True), nullable=True)
    test_status: Any = Column(String(32), nullable=False, default="untested")
    test_message: Any = Column(Text, nullable=True)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
