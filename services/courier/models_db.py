import random
import string
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _generate_login() -> str:
    """Generate unique 6-digit login (digits only, 100000–999999)."""
    return "".join(random.choices(string.digits, k=6))


class CourierModel(Base):
    __tablename__ = "couriers"

    courier_id: Mapped[str] = mapped_column(String(6), primary_key=True)
    kitchen_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline", index=True)
    current_location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    current_orders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # list of UUID strings
    max_batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    orders_delivered_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_delivery_time_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geo_trust_score: Mapped[float] = mapped_column(nullable=False, default=1.0)
    shift_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrival_qr_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    arrival_qr_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
