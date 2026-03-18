from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class OrderContext:
    order_id: UUID
    kitchen_id: UUID
    customer_lat: float
    customer_lon: float
    promised_delivery_time: datetime
    preparation_ready_time: datetime | None = None


@dataclass
class Candidate:
    candidate_id: str  # courier_id or service_id
    is_staff: bool
    # Staff-only
    current_lat: float | None = None
    current_lon: float | None = None
    orders_delivered_today: int = 0
    total_delivery_time_today: int = 0
    shift_start: datetime | None = None
    shift_end: datetime | None = None
    current_orders: list[str] = field(default_factory=list)
    max_batch_size: int = 3
    geo_trust_score: float = 1.0
    name: str = ""
    # 3PL-only
    eta_minutes: float = 0.0
    cost_per_order: float = 0.0
    current_sla_minutes: int = 60


@dataclass
class FactorDetail:
    name: str
    raw_value: Any
    normalized_value: float
    weight: float
    explanation: str


@dataclass
class ScoredCandidate:
    candidate_id: str
    is_staff: bool
    score: float
    factors: list[FactorDetail]
    name: str = ""


@dataclass
class DispatchResult:
    assigned_to: str
    carrier_type: str  # staff | 3pl
    assignment_source: str  # dispatcher_auto
    algorithm_version: str
    scores: dict[str, float]
    winner_score: float
    reason_summary: str
    factors: list[dict[str, Any]]
    context_snapshot: dict[str, Any]
    all_candidates: list[ScoredCandidate]
    used_sla_fallback: bool = False
