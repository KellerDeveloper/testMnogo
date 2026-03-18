from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class PointSchema(BaseModel):
    lat: float
    lon: float


# --- Order events ---


class OrderCreated(BaseModel):
    event_type: str = "order.created"
    order_id: str
    kitchen_id: str
    customer_location: PointSchema
    promised_delivery_time: datetime
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class OrderReadyForDispatch(BaseModel):
    event_type: str = "order.ready_for_dispatch"
    order_id: str
    kitchen_id: str
    customer_location: PointSchema
    promised_delivery_time: datetime
    preparation_ready_time: datetime
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class OrderAssigned(BaseModel):
    event_type: str = "order.assigned"
    order_id: str
    assigned_courier_id: Optional[str] = None
    assigned_carrier_type: Optional[str] = None  # staff | 3pl
    assignment_source: str  # dispatcher_auto | manual_override
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class OrderPickedUp(BaseModel):
    event_type: str = "order.picked_up"
    order_id: str
    courier_id: str
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class OrderDelivered(BaseModel):
    event_type: str = "order.delivered"
    order_id: str
    courier_id: Optional[str] = None
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class OrderCancelled(BaseModel):
    event_type: str = "order.cancelled"
    order_id: str
    reason: Optional[str] = None
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


# --- Courier events ---


class CourierStatusChanged(BaseModel):
    event_type: str = "courier.status_changed"
    courier_id: str
    kitchen_id: str
    status: str  # idle | delivering | returning | offline
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class CourierLocationUpdated(BaseModel):
    event_type: str = "courier.location_updated"
    courier_id: str
    lat: float
    lon: float
    source: str = "gps"  # gps | wifi | cell
    timestamp: datetime = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


# --- Dispatch events ---


class DispatchDecisionMade(BaseModel):
    event_type: str = "dispatch.decision_made"
    decision_id: str
    order_id: str
    assigned_to: str
    carrier_type: str
    assignment_source: str
    algorithm_version: str
    scores: Dict[str, float]
    winner_score: float
    reason_summary: str
    factors: List[Dict[str, Any]]
    context_snapshot: Dict[str, Any]
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)


class DispatchManualOverride(BaseModel):
    event_type: str = "dispatch.manual_override"
    order_id: str
    operator_id: str
    assigned_courier_id: str
    override_reason: Optional[str] = None
    previous_assignment: Optional[Dict[str, Any]] = None
    kitchen_context: Optional[Dict[str, Any]] = None
    created_at: datetime = None

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)
