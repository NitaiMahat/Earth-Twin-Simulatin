from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.domain.action import AudienceType, SimulationMode
from app.models.domain.planning import (
    GeometryPoint,
    InfrastructureCategory,
    MitigationCommitment,
    PlannerProjectType,
    PlanningLocationInput,
)


class ApplyActionRequest(BaseModel):
    zone_id: str
    action_type: str
    intensity: float = Field(ge=0, le=1)
    duration_years: int = Field(ge=1, le=25)
    mode: SimulationMode = SimulationMode.PLANNING


class ProjectionActionRequest(BaseModel):
    zone_id: str
    action_type: str
    intensity: float = Field(ge=0, le=1)
    duration_years: int = Field(ge=1, le=25)


class ProjectFutureRequest(BaseModel):
    base_world_id: str
    actions: list[ProjectionActionRequest]
    projection_years: int = Field(ge=1, le=50)
    mode: SimulationMode = SimulationMode.PLANNING


class AIExplainRequest(BaseModel):
    zone_id: str
    context: str = ""
    question: str
    mode: SimulationMode = SimulationMode.PLANNING
    audience: AudienceType | None = None

    @model_validator(mode="after")
    def apply_default_audience(self) -> "AIExplainRequest":
        if self.audience is not None:
            return self

        if self.mode == SimulationMode.LEARNING:
            self.audience = AudienceType.STUDENT
        else:
            self.audience = AudienceType.PLANNER
        return self


class ScenarioTemplateRunRequest(BaseModel):
    base_world_id: str | None = None
    projection_years: int | None = Field(default=None, ge=1, le=50)
    mode: SimulationMode | None = None


class CompareScenarioRequest(BaseModel):
    name: str
    actions: list[ProjectionActionRequest]


class CompareScenariosRequest(BaseModel):
    base_world_id: str
    projection_years: int = Field(ge=1, le=50)
    mode: SimulationMode = SimulationMode.PLANNING
    scenarios: list[CompareScenarioRequest] = Field(min_length=2)


class ProposalAssessmentRequest(BaseModel):
    location: PlanningLocationInput
    project_type: PlannerProjectType | None = None
    infrastructure_type: InfrastructureCategory | None = None
    geometry_points: list[GeometryPoint] = Field(default_factory=list)
    infrastructure_details: dict[str, Any] = Field(default_factory=dict)
    footprint_acres: float | None = Field(default=None, gt=0, le=5000)
    estimated_daily_vehicle_trips: int | None = Field(default=None, ge=0, le=50000)
    buildout_years: int | None = Field(default=None, ge=1, le=25)
    mitigation_commitment: MitigationCommitment
    planner_notes: str | None = None

    @model_validator(mode="after")
    def validate_assessment_mode(self) -> "ProposalAssessmentRequest":
        uses_infrastructure_flow = self.infrastructure_type is not None
        uses_legacy_flow = (
            self.project_type is not None
            and self.footprint_acres is not None
            and self.estimated_daily_vehicle_trips is not None
            and self.buildout_years is not None
        )

        if not uses_infrastructure_flow and not uses_legacy_flow:
            raise ValueError(
                "Provide either infrastructure_type with infrastructure_details, or project_type with "
                "footprint_acres, estimated_daily_vehicle_trips, and buildout_years."
            )
        return self


class GeometryResolutionRequest(BaseModel):
    location: PlanningLocationInput
    infrastructure_type: InfrastructureCategory
    geometry_points: list[GeometryPoint] = Field(min_length=2)
    infrastructure_details: dict[str, Any] = Field(default_factory=dict)


class GoalToActionsRequest(BaseModel):
    goal: str = Field(min_length=5, max_length=500)
    zone_id: str
    base_world_id: str = "global_continental_baseline"


class SuggestImprovementsRequest(BaseModel):
    goal: str
    zone_id: str
    zone_name: str
    actions: list[dict]
    initial_metrics: dict
    final_metrics: dict
    projection_years: int = Field(ge=1, le=50)
    sustainability_score: float
    overall_outlook: str


class GenerateReportRequest(BaseModel):
    goal: str
    zone_name: str
    zone_type: str = "unknown"
    actions: list[dict]
    initial_metrics: dict
    final_metrics: dict
    projection_years: int = Field(ge=1, le=50)
    sustainability_score: float
    overall_outlook: str
    ai_analysis: str = ""


class TextPlanningOverridesRequest(BaseModel):
    infrastructure_type: InfrastructureCategory | None = None
    project_type: PlannerProjectType | None = None
    infrastructure_details: dict[str, Any] = Field(default_factory=dict)
    footprint_acres: float | None = Field(default=None, gt=0, le=5000)
    estimated_daily_vehicle_trips: int | None = Field(default=None, ge=0, le=50000)
    buildout_years: int | None = Field(default=None, ge=1, le=25)


class SavedTextPlanningSnapshotRequest(BaseModel):
    user_prompt: str = Field(min_length=5, max_length=4000)
    planner_summary: str
    inferred_infrastructure_type: InfrastructureCategory | None = None
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    used_user_overrides: bool = False


class TextPlanningDraftRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    location: PlanningLocationInput | None = None
    geometry_points: list[GeometryPoint] = Field(default_factory=list)
    user_prompt: str = Field(min_length=5, max_length=4000, alias="prompt")
    project_name: str | None = Field(default=None, min_length=3, max_length=120)
    planner_notes: str | None = None


class TextPlanningRunRequest(TextPlanningDraftRequest):
    mitigation_commitment: MitigationCommitment
    confirmed_overrides: TextPlanningOverridesRequest | None = None


class SaveProjectRequest(ProposalAssessmentRequest):
    project_name: str = Field(min_length=3, max_length=120)
    text_planning: SavedTextPlanningSnapshotRequest | None = None


class SaveProjectReportRequest(BaseModel):
    ai_analysis: str | None = None
    pdf_url: str | None = Field(default=None, max_length=2000)
    pdf_filename: str | None = Field(default=None, max_length=255)
    storage_path: str | None = Field(default=None, max_length=1000)
