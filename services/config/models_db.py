from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AlgorithmConfigModel(Base):
    __tablename__ = "algorithm_configs"

    config_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    staff_priority_bonus: Mapped[float] = mapped_column(nullable=False, default=0.20)
    sla_fallback_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kitchen_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KitchenConfigAssignmentModel(Base):
    __tablename__ = "kitchen_config_assignments"

    kitchen_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    config_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
