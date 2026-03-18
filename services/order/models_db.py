from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class OrderModel(Base):
    __tablename__ = "orders"

    order_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    kitchen_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_location: Mapped[dict] = mapped_column(JSONB, nullable=False)
    promised_delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    preparation_ready_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", index=True)
    assigned_courier_id: Mapped[str | None] = mapped_column(String(6), nullable=True)
    assigned_carrier_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assignment_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_orders_kitchen_status", "kitchen_id", "status"),
        Index("ix_orders_promised_delivery", "promised_delivery_time"),
    )
