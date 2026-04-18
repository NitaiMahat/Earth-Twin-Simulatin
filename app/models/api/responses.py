from __future__ import annotations

from pydantic import BaseModel

from app.models.domain.action import AudienceType, SimulationMode
from app.models.domain.planning import MitigationCommitment, PlanVerdict, PlannerProjectType
from app.models.domain.scenario_template import ScenarioTemplateAction
from app.models.domain.simulation import CompactZoneSummary
from app.models.domain.world import WorldState
from app.models.domain.zone import ZoneState


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class WorldStateResponse(BaseModel):
    world: WorldState


class WorldResetResponse(BaseModel):
    message: str
    world: WorldState


class ZoneListResponse(BaseModel):
    zones: list[ZoneState]
    count: int


class ZoneDetailResponse(BaseModel):
    zone: ZoneState
    risk_summary: str
    top_drivers: list[str]
    recommended_focus: str


class AppliedActionResponse(BaseModel):
    action_type: str
    intensity: float
    duration_years: int


class MetricDeltaResponse(BaseModel):
    tree_cover: float
    biodiversity_score: float
    pollution_level: float
    traffic_level: float
    temperature: float
    ecosystem_health: float


class ApplyActionResponse(BaseModel):
    zone_id: str
    requested_action_type: str
    normalized_action_type: str
    mode: SimulationMode
    applied_action: AppliedActionResponse
    before: ZoneState
    after: ZoneState
    delta: MetricDeltaResponse
    deltas: MetricDeltaResponse
    derived_effects: list[str]
    risk_level: str
    sustainability_score: float
    summary_text: str
    top_drivers: list[str]


class ProjectFutureResponse(BaseModel):
    projection_years: int
    mode: SimulationMode
    summary: str
    summary_text: str
    projected_zones: list[ZoneState]
    highest_risk_zone: ZoneState | None
    highest_risk_zone_top_drivers: list[str]
    avg_biodiversity_drop: float
    avg_temperature_change: float
    sustainability_score: float
    overall_outlook: str
    recommended_focus: str


class AIExplainResponse(BaseModel):
    answer: str
    bullets: list[str]
    recommended_actions: list[str]
    tone: str
    audience: AudienceType
    mode: SimulationMode


class ScenarioTemplateResponse(BaseModel):
    template_id: str
    name: str
    mode: SimulationMode
    description: str
    recommended_audience: AudienceType
    default_projection_years: int
    default_actions: list[ScenarioTemplateAction]
    objective: str
    product_focus: str
    difficulty: str


class ScenarioTemplateListResponse(BaseModel):
    templates: list[ScenarioTemplateResponse]
    count: int


class ScenarioTemplateDetailResponse(BaseModel):
    template: ScenarioTemplateResponse


class ScenarioTemplateRunResponse(ProjectFutureResponse):
    template_id: str
    template_name: str
    objective: str
    product_focus: str


class ComparedScenarioResponse(BaseModel):
    name: str
    summary: str
    summary_text: str
    highest_risk_zone: CompactZoneSummary | None
    avg_biodiversity_drop: float
    avg_temperature_change: float
    sustainability_score: float
    overall_outlook: str
    recommended_focus: str


class CompareScenariosResponse(BaseModel):
    mode: SimulationMode
    projection_years: int
    scenarios: list[ComparedScenarioResponse]
    recommended_scenario: str | None
    key_tradeoffs: list[str]
    comparison_summary_text: str


class PlanningAreaResponse(BaseModel):
    area_id: str
    name: str
    baseline_zone_id: str
    current_risk_level: str
    planning_notes: str
    allowed_project_types: list[PlannerProjectType]


class PlanningSiteResponse(BaseModel):
    site_id: str
    name: str
    state: str
    summary: str
    areas: list[PlanningAreaResponse]


class PlannerSimulationActionResponse(BaseModel):
    zone_id: str
    requested_action_type: str
    normalized_action_type: str
    intensity: float
    duration_years: int


class PlannerSimulationInputsResponse(BaseModel):
    projection_years: int
    baseline_zone_id: str
    footprint_bucket: str
    traffic_bucket: str
    submitted_actions: list[PlannerSimulationActionResponse]
    mitigated_actions: list[PlannerSimulationActionResponse]


class PlanScorecardResponse(BaseModel):
    plan_score: float
    verdict: PlanVerdict
    overall_outlook: str
    highest_risk_zone: CompactZoneSummary | None
    top_risks: list[str]
    required_mitigations: list[str]
    summary_text: str


class ProposalAssessmentResponse(BaseModel):
    site_id: str
    area_id: str
    project_type: PlannerProjectType
    footprint_acres: float
    estimated_daily_vehicle_trips: int
    buildout_years: int
    mitigation_commitment: MitigationCommitment
    planner_notes: str | None
    submitted_plan: PlanScorecardResponse
    mitigated_plan: PlanScorecardResponse
    recommended_option: str
    comparison_summary: str
    simulation_inputs: PlannerSimulationInputsResponse
