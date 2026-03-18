from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class AlgorithmConfig(BaseModel):
    config_id: UUID
    version: str
    name: str
    description: str = ""
    weights: Dict[str, float] = {}
    staff_priority_bonus: float = 0.20
    sla_fallback_threshold: int = 5
    is_active: bool = False
    kitchen_ids: List[UUID] = []
    created_by: str = ""
    approved_by: Optional[str] = None
