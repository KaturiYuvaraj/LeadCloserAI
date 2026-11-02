from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.sql import func
from core.db import Base


class ProviderSetting(Base):
    __tablename__ = "provider_settings"

    provider_type = Column(String(64), primary_key=True)
    provider_name = Column(String(64), primary_key=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_configured = Column(Boolean, nullable=False, default=False)
    config_json = Column(Text, nullable=False, default="{}")
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    test_status = Column(String(32), nullable=False, default="untested")
    test_message = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
