from typing import Any
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from core.db import Base


class Number(Base):
    __tablename__ = "numbers"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    e164: Any = Column(String(32), unique=True, nullable=False, index=True)
    provider: Any = Column(String(32), nullable=False, default="vobiz")
    channels: Any = Column(Integer, nullable=False, default=10)
    is_test_line: Any = Column(Boolean, nullable=False, default=False)
    employee_id: Any = Column(Integer, nullable=True, index=True)
    status: Any = Column(String(32), nullable=False, default="active")
