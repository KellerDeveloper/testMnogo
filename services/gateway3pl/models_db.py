from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Float, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ThirdPartyProviderModel(Base):
    __tablename__ = "third_party_providers"

    service_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kitchen_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    avg_pickup_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    avg_delivery_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    current_sla_minutes: Mapped[int] = mapped_column(Integer, default=60)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
