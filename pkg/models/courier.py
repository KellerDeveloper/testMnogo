from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .order import Point


class CourierStatus(str, Enum):
    IDLE = "idle"
    DELIVERING = "delivering"
    RETURNING = "returning"
    OFFLINE = "offline"


class Courier(BaseModel):
    courier_id: UUID
    kitchen_id: UUID
    name: str
    status: CourierStatus = CourierStatus.OFFLINE
    current_location: Optional[Point] = None
    current_orders: List[UUID] = Field(default_factory=list)
    max_batch_size: int = 3
    orders_delivered_today: int = 0
    total_delivery_time_today: int = 0  # minutes
    geo_trust_score: float = 1.0
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None


class CourierCreate(BaseModel):
    kitchen_id: UUID
    name: str
    max_batch_size: int = 3
