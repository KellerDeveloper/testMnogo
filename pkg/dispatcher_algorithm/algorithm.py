"""
Weighted scoring dispatcher algorithm.
Factors: delivery_time (0.40), fairness (0.25), distance (0.15), batch (0.10), geo_trust (0.10).
Staff priority bonus +0.20. SLA fallback to 3PL when staff cannot meet deadline.
"""
import math
from datetime import datetime, timezone
from typing import Any

from .types import (
    OrderContext,
    Candidate,
    ScoredCandidate,
    DispatchResult,
    FactorDetail,
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def normalize_delivery_time(
    order: OrderContext,
    candidate: Candidate,
    kitchen_lat: float,
    kitchen_lon: float,
) -> tuple[float, float, str]:
    """Score 1.0 = deliver well before deadline, 0.0 = after deadline. Returns (score, eta_minutes, explanation)."""
    if candidate.is_staff:
        if candidate.current_lat is None:
            return 0.5, 0.0, "Нет координат курьера"
        dist_to_kitchen_km = haversine_km(
            candidate.current_lat, candidate.current_lon, kitchen_lat, kitchen_lon
        )
        dist_to_customer_km = haversine_km(
            kitchen_lat, kitchen_lon, order.customer_lat, order.customer_lon
        )
        # Rough: 20 km/h average, then 15 min at customer
        eta_minutes = (dist_to_kitchen_km + dist_to_customer_km) / 20 * 60 + 15
    else:
        eta_minutes = candidate.eta_minutes
    deadline = order.promised_delivery_time
    if hasattr(deadline, "tzinfo") and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    minutes_to_deadline = (deadline - now).total_seconds() / 60
    if minutes_to_deadline <= 0:
        return 0.0, eta_minutes, "Дедлайн уже прошёл"
    if eta_minutes <= minutes_to_deadline - 15:
        return 1.0, eta_minutes, f"Доставка за ~{int(eta_minutes)} мин, до дедлайна {int(minutes_to_deadline)} мин"
    if eta_minutes >= minutes_to_deadline:
        return 0.0, eta_minutes, f"Не успеем: ETA {int(eta_minutes)} мин, дедлайн через {int(minutes_to_deadline)} мин"
    # Linear between
    score = (minutes_to_deadline - eta_minutes) / 15
    score = max(0.0, min(1.0, score))
    return score, eta_minutes, f"ETA {int(eta_minutes)} мин, дедлайн через {int(minutes_to_deadline)} мин"


def normalize_fairness(candidates: list[Candidate], candidate: Candidate) -> tuple[float, str]:
    """1.0 = least loaded, 0.0 = most loaded. workload_ratio = orders_delivered / hours_on_shift."""
    staff = [c for c in candidates if c.is_staff]
    if not staff or not candidate.is_staff:
        return 1.0, "Не применимо"
    hours = []
    for c in staff:
        if c.shift_start:
            end = c.shift_end or datetime.now(timezone.utc)
            if hasattr(end, "tzinfo") and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if hasattr(c.shift_start, "tzinfo") and c.shift_start.tzinfo is None:
                start = c.shift_start.replace(tzinfo=timezone.utc)
            else:
                start = c.shift_start
            h = (end - start).total_seconds() / 3600 or 0.01
        else:
            h = 0.01
        orders = c.orders_delivered_today or 0
        hours.append((c.candidate_id, orders / h))
    if not hours:
        return 1.0, "Нет данных"
    ratios = [r for _, r in hours]
    min_r = min(ratios)
    max_r = max(ratios)
    cand_ratio = next((r for id_, r in hours if id_ == candidate.candidate_id), min_r)
    if max_r <= min_r:
        return 1.0, "Равная загрузка"
    score = 1.0 - (cand_ratio - min_r) / (max_r - min_r)
    return max(0.0, min(1.0, score)), f"Заказов/час: {cand_ratio:.1f}"


def normalize_distance(
    candidate: Candidate,
    kitchen_lat: float,
    kitchen_lon: float,
) -> tuple[float, str]:
    """1.0 = at kitchen, 0.0 = farthest."""
    if not candidate.is_staff or candidate.current_lat is None:
        return 0.5, "Нет координат"
    dist_km = haversine_km(
        candidate.current_lat, candidate.current_lon, kitchen_lat, kitchen_lon
    )
    # 5 km = 0, 0 km = 1
    score = max(0.0, 1.0 - dist_km / 5.0)
    return score, f"Расстояние до кухни {dist_km:.1f} км"


def normalize_batch(
    order: OrderContext,
    candidate: Candidate,
    kitchen_lat: float,
    kitchen_lon: float,
) -> tuple[float, str]:
    """1.0 = same direction, 0.0 = no compatibility."""
    if not candidate.is_staff or not candidate.current_orders:
        return 0.5, "Нет текущих заказов"
    # Simplified: if courier has orders, slight bonus for being active in same area
    return 0.7, "Курьер уже в доставке"


def normalize_geo_trust(candidate: Candidate) -> tuple[float, str]:
    """1.0 = full trust, 0.0 = no trust."""
    if not candidate.is_staff:
        return 1.0, "3PL"
    s = candidate.geo_trust_score
    return s, f"Trust score {s:.2f}"


class DispatcherAlgorithm:
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        staff_priority_bonus: float = 0.20,
        sla_fallback_threshold_minutes: int = 5,
        algorithm_version: str = "v1.0",
    ):
        self.weights = weights or {
            "delivery_time": 0.40,
            "fairness": 0.25,
            "distance": 0.15,
            "batch": 0.10,
            "geo_trust": 0.10,
        }
        self.staff_priority_bonus = staff_priority_bonus
        self.sla_fallback_threshold = sla_fallback_threshold_minutes
        self.algorithm_version = algorithm_version

    def score_candidates(
        self,
        order: OrderContext,
        candidates: list[Candidate],
        kitchen_lat: float,
        kitchen_lon: float,
    ) -> list[ScoredCandidate]:
        scored = []
        for c in candidates:
            factors = []
            dt_score, eta, dt_expl = normalize_delivery_time(
                order, c, kitchen_lat, kitchen_lon
            )
            factors.append(FactorDetail(
                "delivery_time", eta, dt_score, self.weights["delivery_time"], dt_expl
            ))
            fair_score, fair_expl = normalize_fairness(candidates, c)
            factors.append(FactorDetail(
                "fairness", None, fair_score, self.weights["fairness"], fair_expl
            ))
            dist_score, dist_expl = normalize_distance(c, kitchen_lat, kitchen_lon)
            factors.append(FactorDetail(
                "distance", None, dist_score, self.weights["distance"], dist_expl
            ))
            batch_score, batch_expl = normalize_batch(
                order, c, kitchen_lat, kitchen_lon
            )
            factors.append(FactorDetail(
                "batch", None, batch_score, self.weights["batch"], batch_expl
            ))
            geo_score, geo_expl = normalize_geo_trust(c)
            factors.append(FactorDetail(
                "geo_trust", None, geo_score, self.weights["geo_trust"], geo_expl
            ))
            total = sum(f.normalized_value * f.weight for f in factors)
            if c.is_staff:
                total += self.staff_priority_bonus
            scored.append(ScoredCandidate(
                candidate_id=c.candidate_id,
                is_staff=c.is_staff,
                score=round(total, 4),
                factors=factors,
                name=c.name,
            ))
        return sorted(scored, key=lambda x: -x.score)

    def build_reason_summary(
        self,
        winner: ScoredCandidate,
        runners_up: list[ScoredCandidate],
        order: OrderContext,
    ) -> str:
        parts = [f"{winner.name or winner.candidate_id} выбран: "]
        for f in winner.factors[:3]:
            parts.append(f"{f.name}={f.normalized_value:.2f} ({f.explanation}). ")
        parts.append(f"Скор: {winner.score:.2f}. ")
        if runners_up:
            next_c = runners_up[0]
            parts.append(f"Следующий кандидат: {next_c.name or next_c.candidate_id} ({next_c.score:.2f}).")
        return "".join(parts)

    def run(
        self,
        order: OrderContext,
        candidates: list[Candidate],
        kitchen_lat: float,
        kitchen_lon: float,
    ) -> DispatchResult:
        if not candidates:
            raise ValueError("No candidates")
        scored = self.score_candidates(order, candidates, kitchen_lat, kitchen_lon)
        winner = scored[0]
        runners_up = scored[1:]
        scores_dict = {s.candidate_id: s.score for s in scored}
        factors_serialized = []
        for f in winner.factors:
            factors_serialized.append({
                "name": f.name,
                "raw_value": f.raw_value,
                "normalized_value": f.normalized_value,
                "weight": f.weight,
                "explanation": f.explanation,
            })
        reason = self.build_reason_summary(winner, runners_up, order)
        context_snapshot = {
            "order_id": str(order.order_id),
            "kitchen_id": str(order.kitchen_id),
            "candidate_count": len(candidates),
            "staff_count": sum(1 for c in candidates if c.is_staff),
            "3pl_count": sum(1 for c in candidates if not c.is_staff),
        }
        used_sla_fallback = False
        carrier_type = "staff" if winner.is_staff else "3pl"
        # SLA fallback: if best staff cannot meet deadline, prefer 3PL that can
        best_staff = next((s for s in scored if s.is_staff), None)
        best_3pl = next((s for s in scored if not s.is_staff), None)
        if best_staff and best_3pl:
            deadline = order.promised_delivery_time
            if hasattr(deadline, "tzinfo") and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            minutes_to_deadline = (deadline - now).total_seconds() / 60
            # If best staff score is low on delivery_time and 3PL can deliver in time, switch
            staff_dt = next(
                (f.normalized_value for f in best_staff.factors if f.name == "delivery_time"),
                0.0,
            )
            if minutes_to_deadline < self.sla_fallback_threshold + 10 and staff_dt < 0.5 and best_3pl.score >= 0.5:
                winner = best_3pl
                runners_up = [s for s in scored if s.candidate_id != winner.candidate_id]
                scores_dict = {s.candidate_id: s.score for s in scored}
                reason = f"SLA fallback: 3PL {winner.name or winner.candidate_id} выбран для соблюдения дедлайна. " + reason
                factors_serialized = [{"name": f.name, "raw_value": f.raw_value, "normalized_value": f.normalized_value, "weight": f.weight, "explanation": f.explanation} for f in winner.factors]
                carrier_type = "3pl"
                used_sla_fallback = True
        return DispatchResult(
            assigned_to=winner.candidate_id,
            carrier_type=carrier_type,
            assignment_source="dispatcher_auto",
            algorithm_version=self.algorithm_version,
            scores=scores_dict,
            winner_score=winner.score,
            reason_summary=reason,
            factors=factors_serialized,
            context_snapshot=context_snapshot,
            all_candidates=scored,
            used_sla_fallback=used_sla_fallback,
        )
