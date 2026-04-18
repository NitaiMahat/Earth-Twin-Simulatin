from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.domain.planning import GeometryPoint, InfrastructureCategory, MitigationCommitment, PlannerProjectType


class BuilderRole(str, Enum):
    BUILDER = "builder"
    EDUCATOR = "educator"


class AuthProvider(str, Enum):
    DEMO_OIDC = "demo_oidc"


class BuilderIdentity(BaseModel):
    token: str
    provider: AuthProvider = AuthProvider.DEMO_OIDC
    subject: str
    email: str
    display_name: str
    organization_id: str
    role: BuilderRole


class BuilderManagedAreaDefinition(BaseModel):
    area_id: str
    name: str
    baseline_zone_id: str
    planning_notes: str
    allowed_project_types: list[PlannerProjectType]


class BuilderManagedSiteDefinition(BaseModel):
    site_id: str
    planning_site_id: str
    name: str
    country: str
    state: str
    summary: str
    areas: list[BuilderManagedAreaDefinition]


class BuilderProjectStatus(str, Enum):
    DRAFT = "draft"
    SIMULATED = "simulated"


class BuilderProjectProposal(BaseModel):
    site_id: str
    area_id: str
    project_type: PlannerProjectType | None = None
    infrastructure_type: InfrastructureCategory | None = None
    geometry_points: list[GeometryPoint] = Field(default_factory=list)
    infrastructure_details: dict[str, str | int | float | bool] = Field(default_factory=dict)
    footprint_acres: float | None = None
    estimated_daily_vehicle_trips: int | None = None
    buildout_years: int | None = None
    mitigation_commitment: MitigationCommitment
    planner_notes: str | None = None


class BuilderProjectSnapshot(BaseModel):
    snapshot_id: str
    created_at: str
    report_payload: dict[str, Any]


class BuilderProjectRecord(BaseModel):
    project_id: str
    project_name: str
    owner_subject: str
    owner_email: str
    organization_id: str
    status: BuilderProjectStatus = BuilderProjectStatus.DRAFT
    proposal: BuilderProjectProposal
    latest_report_payload: dict[str, Any] | None = None
    latest_snapshot_id: str | None = None
    history: list[BuilderProjectSnapshot] = Field(default_factory=list)
    created_at: str
    updated_at: str
