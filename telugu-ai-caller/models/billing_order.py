from typing import Any
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class BillingOrder(Base):
    __tablename__ = "api_billing_orders"

    id: Any = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Any = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    api_key_id: Any = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Any = Column(String(128), unique=True, nullable=False, index=True)
    plan_name: Any = Column(String(128), nullable=False)
    amount_inr: Any = Column(Float, nullable=False)
    minutes_credited: Any = Column(Float, nullable=False)
    payment_method: Any = Column(String(64), nullable=False, default="UPI / Razorpay")
    payment_status: Any = Column(String(32), nullable=False, default="success")
    customer_email: Any = Column(String(255), nullable=True)
    invoice_number: Any = Column(String(128), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
