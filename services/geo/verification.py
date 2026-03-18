"""
Antifraud verification: levels 1-5.
Level 1: Physical plausibility (speed check)
Level 2: Multi-source consistency (stub - would need wifi/cell data)
Level 3: Historical continuity (gap penalty)
Level 4: Zone checks (stub - would need order zones)
Level 5: Dynamic trust score
"""
import math
from datetime import datetime, timezone
from typing import Optional

from config import settings


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def level1_speed_check(
    lat: float, lon: float, ts: datetime,
    prev_lat: Optional[float], prev_lon: Optional[float], prev_ts: Optional[datetime],
) -> tuple[bool, float]:
    """Returns (accepted, speed_kmh). Reject if speed > max_speed_kmh."""
    if prev_lat is None or prev_ts is None:
        return True, 0.0
    dist_km = haversine_km(prev_lat, prev_lon, lat, lon)
    dt_h = (ts - prev_ts).total_seconds() / 3600
    if dt_h <= 0:
        return False, 0.0
    speed_kmh = dist_km / dt_h
    return speed_kmh <= settings.max_speed_kmh, speed_kmh


def level3_gap_penalty(prev_ts: Optional[datetime], ts: datetime) -> float:
    """Return penalty 0..1 for gap > gap_penalty_minutes."""
    if prev_ts is None:
        return 0.0
    gap_min = (ts - prev_ts).total_seconds() / 60
    if gap_min <= settings.gap_penalty_minutes:
        return 0.0
    return min(1.0, (gap_min - settings.gap_penalty_minutes) / 30)


def update_trust_score(
    current_trust: float,
    speed_ok: bool,
    gap_penalty: float,
    multi_source_ok: bool = True,
) -> float:
    """Level 5: dynamic trust score in [0, 1]."""
    delta = 0.0
    if not speed_ok:
        delta -= settings.trust_penalty_rate
    if gap_penalty > 0:
        delta -= gap_penalty * settings.trust_penalty_rate
    if not multi_source_ok:
        delta -= settings.trust_penalty_rate
    if speed_ok and gap_penalty == 0 and multi_source_ok:
        delta += settings.trust_recovery_rate
    return max(0.0, min(1.0, current_trust + delta))
