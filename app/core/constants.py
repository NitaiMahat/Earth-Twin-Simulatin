from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


ZONE_VALUE_MIN = 0.0
ZONE_VALUE_MAX = 100.0
ZONE_TEMPERATURE_MIN = -10.0
ZONE_TEMPERATURE_MAX = 60.0

WORLD_TEMPERATURE_BASE = 14.0
WORLD_CO2_BASE = 360.0
PASSIVE_WARMING_PER_YEAR = 0.03

RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

SUSTAINABILITY_RISK_PENALTY = {
    RiskLevel.LOW: 0.0,
    RiskLevel.MEDIUM: 6.0,
    RiskLevel.HIGH: 12.0,
    RiskLevel.CRITICAL: 18.0,
}
