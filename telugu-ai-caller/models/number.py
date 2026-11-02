from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from core.db import Base


class Number(Base):
    __tablename__ = "numbers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    e164 = Column(String(32), unique=True, nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="exotel")
    channels = Column(Integer, nullable=False, default=1)
    is_test_line = Column(Boolean, nullable=False, default=False)
    employee_id = Column(Integer, nullable=True, index=True)
    status = Column(String(32), nullable=False, default="active")
