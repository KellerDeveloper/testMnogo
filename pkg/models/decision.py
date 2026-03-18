from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from .order import AssignmentSource, CarrierType


class OverrideInfo(BaseModel):
    operator_id: str
    override_reason: Optional[str] = None
    previous_assignment: Optional[Dict[str, Any]] = None
    timestamp: datetime
    kitchen_context: Optional[Dict[str, Any]] = None


class DispatchDecision(BaseModel):
    decision_id: UUID
    order_id: UUID
    timestamp: datetime
    assigned_to: UUID
    carrier_type: CarrierType
    assignment_source: AssignmentSource
    algorithm_version: str
    scores: Dict[str, float]
    winner_score: float
    reason_summary: str
    factors: List[Dict[str, Any]]
    context_snapshot: Dict[str, Any]
    override_info: Optional[OverrideInfo] = None
