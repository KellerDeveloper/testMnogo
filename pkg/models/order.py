from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    NEW = "new"
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CarrierType(str, Enum):
    STAFF = "staff"
    THREEPL = "3pl"


class AssignmentSource(str, Enum):
    DISPATCHER_AUTO = "dispatcher_auto"
    MANUAL_OVERRIDE = "manual_override"


class Point(BaseModel):
    lat: float
    lon: float


class Order(BaseModel):
    order_id: UUID
    kitchen_id: UUID
    customer_location: Point
    promised_delivery_time: datetime
    preparation_ready_time: Optional[datetime] = None
    status: OrderStatus = OrderStatus.NEW
    assigned_courier_id: Optional[UUID] = None
    assigned_carrier_type: Optional[CarrierType] = None
    assignment_source: Optional[AssignmentSource] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrderCreate(BaseModel):
    kitchen_id: UUID
    customer_location: Point
    promised_delivery_time: datetime
    preparation_ready_time_estimate_minutes: Optional[int] = None
