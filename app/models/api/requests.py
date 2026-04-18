from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.domain.action import AudienceType, SimulationMode
from app.models.domain.planning import MitigationCommitment, PlannerProjectType


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
    site_id: str
    area_id: str
    project_type: PlannerProjectType
    footprint_acres: float = Field(gt=0, le=5000)
    estimated_daily_vehicle_trips: int = Field(ge=0, le=50000)
    buildout_years: int = Field(ge=1, le=25)
    mitigation_commitment: MitigationCommitment
    planner_notes: str | None = None
