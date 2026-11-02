from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.db import Base


class BillingOrder(Base):
    __tablename__ = "api_billing_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id = Column(String(128), unique=True, nullable=False, index=True)
    plan_name = Column(String(128), nullable=False)
    amount_inr = Column(Float, nullable=False)
    minutes_credited = Column(Float, nullable=False)
    payment_method = Column(String(64), nullable=False, default="UPI / Razorpay")
    payment_status = Column(String(32), nullable=False, default="success")
    customer_email = Column(String(255), nullable=True)
    invoice_number = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
