from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ThirdPartyService(BaseModel):
    service_id: UUID
    name: str
    kitchen_id: UUID
    is_available: bool = True
    avg_pickup_time_minutes: float = 0.0
    avg_delivery_time_minutes: float = 0.0
    cost_per_order: Decimal = Decimal("0")
    current_sla_minutes: int = 60
    success_rate: float = 1.0
