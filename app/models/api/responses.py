from __future__ import annotations

from pydantic import BaseModel

from app.models.domain.action import AudienceType, SimulationMode
from app.models.domain.planning import (
    BuildSectionDefinition,
    GeometryPoint,
    InfrastructureCategory,
    MitigationCommitment,
    PlanVerdict,
    PlannerProjectType,
    PlanningLocationContext,
)
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


class PlanningContinentResponse(BaseModel):
    continent_id: str
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
    continents: list[PlanningContinentResponse]
    build_sections: list[BuildSectionDefinition]


class PlanningBuildOptionsResponse(BaseModel):
    site_id: str
    sections: list[BuildSectionDefinition]


class GeometryLocationSummaryResponse(BaseModel):
    selection_mode: str
    point_count: int
    start_point: GeometryPoint | None
    end_point: GeometryPoint | None
    center_point: GeometryPoint
    length_m: float | None
    area_sq_m: float | None


class PlanningLocationContextResponse(BaseModel):
    label: str
    latitude: float
    longitude: float
    continent_id: str
    continent_name: str
    baseline_zone_id: str
    country_code: str | None = None
    country_name: str | None = None
    state_name: str | None = None
    source_summary: str


class GeometryResolutionResponse(BaseModel):
    location_context: PlanningLocationContextResponse
    infrastructure_type: InfrastructureCategory
    resolved_project_type: PlannerProjectType
    geometry_summary: GeometryLocationSummaryResponse
    resolved_infrastructure_details: dict[str, str | int | float | bool]


class PlannerSimulationActionResponse(BaseModel):
    zone_id: str
    requested_action_type: str
    normalized_action_type: str
    intensity: float
    duration_years: int


class PlannerSimulationInputsResponse(BaseModel):
    projection_years: int
    baseline_zone_id: str
    continent_id: str
    footprint_bucket: str
    traffic_bucket: str
    resolved_project_type: PlannerProjectType
    location_context: PlanningLocationContextResponse
    infrastructure_type: InfrastructureCategory | None
    geometry_summary: GeometryLocationSummaryResponse | None
    infrastructure_details: dict[str, str | int | float | bool]
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


class AnalysisMetricCardResponse(BaseModel):
    label: str
    unit: str | None = None
    baseline_value: float
    submitted_value: float
    mitigated_value: float
    lower_is_better: bool = False


class AnalysisSectionResponse(BaseModel):
    executive_summary: str
    key_findings: list[str]
    improvement_recommendations: list[str]
    long_term_outlook: str


class ProjectAnalysisDocumentResponse(BaseModel):
    title: str
    simulated_project_summary: str
    summary: str
    recommended_option: str
    generated_at: str
    metric_cards: list[AnalysisMetricCardResponse]
    submitted_top_risks: list[str]
    mitigated_top_risks: list[str]
    ai_analysis: str | None = None
    sections: AnalysisSectionResponse


class ProposalAssessmentResponse(BaseModel):
    location_context: PlanningLocationContextResponse
    continent_id: str
    project_type: PlannerProjectType
    infrastructure_type: InfrastructureCategory | None
    geometry_summary: GeometryLocationSummaryResponse | None
    infrastructure_details: dict[str, str | int | float | bool]
    footprint_acres: float
    estimated_daily_vehicle_trips: int
    buildout_years: int
    mitigation_commitment: MitigationCommitment
    planner_notes: str | None
    submitted_plan: PlanScorecardResponse
    mitigated_plan: PlanScorecardResponse
    recommended_option: str
    comparison_summary: str
    analysis_document: ProjectAnalysisDocumentResponse
    simulation_inputs: PlannerSimulationInputsResponse


class SuggestedGeometryPoint(BaseModel):
    latitude: float
    longitude: float
    label: str


class TextPlanningExtractionResponse(BaseModel):
    location_context: PlanningLocationContextResponse
    geometry_summary: GeometryLocationSummaryResponse
    infrastructure_type: InfrastructureCategory | None
    project_type: PlannerProjectType | None
    planner_summary: str
    infrastructure_details: dict[str, str | int | float | bool]
    footprint_acres: float | None
    estimated_daily_vehicle_trips: int | None
    buildout_years: int | None
    missing_fields: list[str]
    assumptions: list[str]
    confidence: float
    simulation_ready: bool
    resolved_zone_id: str | None = None
    resolved_location_label: str | None = None
    suggested_geometry_points: list[SuggestedGeometryPoint] = []


class TextPlanningRunResponse(BaseModel):
    extraction: TextPlanningExtractionResponse
    assessment: ProposalAssessmentResponse


class GoalActionItem(BaseModel):
    action_type: str
    intensity: float
    duration_years: int


class GoalToActionsResponse(BaseModel):
    goal: str
    zone_id: str
    actions: list[GoalActionItem]


class SuggestImprovementsResponse(BaseModel):
    analysis: str


class AuthMeResponse(BaseModel):
    user_id: str
    email: str | None = None
    role: str
    org_id: str | None = None


class ProjectReportMetadataResponse(BaseModel):
    ai_analysis: str | None = None
    pdf_url: str | None = None
    pdf_filename: str | None = None
    storage_path: str | None = None
    updated_at: str | None = None


class SavedTextPlanningSnapshotResponse(BaseModel):
    user_prompt: str
    planner_summary: str
    inferred_infrastructure_type: InfrastructureCategory | None = None
    assumptions: list[str]
    missing_fields: list[str]
    used_user_overrides: bool


class SavedProjectSummaryResponse(BaseModel):
    project_id: str
    project_name: str
    created_at: str
    updated_at: str
    continent_id: str
    project_type: PlannerProjectType
    infrastructure_type: InfrastructureCategory | None
    location_label: str
    recommended_option: str
    project_summary: str | None = None
    latest_report: ProjectReportMetadataResponse


class SavedProjectDetailResponse(BaseModel):
    project_id: str
    project_name: str
    created_at: str
    updated_at: str
    assessment: ProposalAssessmentResponse
    latest_report: ProjectReportMetadataResponse
    text_planning: SavedTextPlanningSnapshotResponse | None = None


class SavedProjectListResponse(BaseModel):
    projects: list[SavedProjectSummaryResponse]
    count: int
