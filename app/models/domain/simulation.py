from __future__ import annotations

from pydantic import BaseModel

from app.core.constants import RiskLevel
from app.models.domain.action import ActionType, SimulationMode
from app.models.domain.world import WorldState
from app.models.domain.zone import ZoneState


class DerivedEffects(BaseModel):
    tree_cover_delta: float
    biodiversity_delta: float
    pollution_delta: float
    traffic_delta: float
    temperature_delta: float
    ecosystem_health_delta: float


class ActionSimulationResult(BaseModel):
    zone_id: str
    action_type: ActionType
    before_state: ZoneState
    after_state: ZoneState
    derived_effects: DerivedEffects
    risk_level: RiskLevel


class ProjectionMetrics(BaseModel):
    highest_risk_zone: ZoneState | None
    average_biodiversity_drop: float
    average_temperature_change: float


class ProjectionSimulationResult(BaseModel):
    projected_world: WorldState
    mode: SimulationMode
    summary: str
    summary_text: str
    highest_risk_zone: ZoneState | None
    highest_risk_zone_top_drivers: list[str]
    avg_biodiversity_drop: float
    avg_temperature_change: float
    sustainability_score: float
    overall_outlook: str
    recommended_focus: str


class CompactZoneSummary(BaseModel):
    zone_id: str
    name: str
    risk_level: RiskLevel
    sustainability_score: float


class ComparedScenarioResult(BaseModel):
    name: str
    summary: str
    summary_text: str
    highest_risk_zone: CompactZoneSummary | None
    avg_biodiversity_drop: float
    avg_temperature_change: float
    sustainability_score: float
    overall_outlook: str
    recommended_focus: str


class ComparisonSimulationResult(BaseModel):
    mode: SimulationMode
    projection_years: int
    scenarios: list[ComparedScenarioResult]
    recommended_scenario: str | None
    key_tradeoffs: list[str]
    comparison_summary_text: str
