from __future__ import annotations

from app.core.constants import (
    ZONE_TEMPERATURE_MAX,
    ZONE_TEMPERATURE_MIN,
    ZONE_VALUE_MAX,
    ZONE_VALUE_MIN,
)
from app.models.domain.zone import ZoneState


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 2)


def apply(zone: ZoneState, intensity: float, duration_years: int) -> ZoneState:
    factor = intensity * duration_years
    zone.traffic_level += 10.0 * factor
    zone.pollution_level += 6.0 * factor
    zone.temperature += 0.25 * factor
    zone.biodiversity_score -= 2.5 * factor
    zone.ecosystem_health -= 4.5 * factor
    zone.traffic_level = _clamp(zone.traffic_level, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
    zone.pollution_level = _clamp(zone.pollution_level, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
    zone.temperature = _clamp(zone.temperature, ZONE_TEMPERATURE_MIN, ZONE_TEMPERATURE_MAX)
    zone.biodiversity_score = _clamp(zone.biodiversity_score, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
    zone.ecosystem_health = _clamp(zone.ecosystem_health, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
    return zone
