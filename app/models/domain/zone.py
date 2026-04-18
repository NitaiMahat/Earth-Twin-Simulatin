from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.core.constants import RiskLevel


class ZoneType(str, Enum):
    CONTINENT = "continent"
    FOREST = "forest"
    CITY = "city"
    INDUSTRIAL = "industrial"
    COASTAL = "coastal"
    AGRICULTURAL = "agricultural"
    WETLAND = "wetland"


class ZoneState(BaseModel):
    zone_id: str
    name: str
    type: ZoneType
    scope: str = "continent"
    latitude: float | None = None
    longitude: float | None = None
    reference_country_code: str | None = None
    source_summary: str | None = None
    tree_cover: float = Field(ge=0, le=100)
    biodiversity_score: float = Field(ge=0, le=100)
    pollution_level: float = Field(ge=0, le=100)
    traffic_level: float = Field(ge=0, le=100)
    temperature: float
    ecosystem_health: float = Field(ge=0, le=100)
    risk_level: RiskLevel = RiskLevel.LOW
    sustainability_score: float = Field(default=0, ge=0, le=100)
