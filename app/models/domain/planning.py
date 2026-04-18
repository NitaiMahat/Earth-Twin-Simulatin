from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class PlannerProjectType(str, Enum):
    INDUSTRIAL_FACILITY = "industrial_facility"
    ROADWAY_LOGISTICS_EXPANSION = "roadway_logistics_expansion"
    MIXED_USE_REDEVELOPMENT = "mixed_use_redevelopment"


class MitigationCommitment(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanVerdict(str, Enum):
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    NOT_RECOMMENDED = "not_recommended"


class PlanningAreaDefinition(BaseModel):
    area_id: str
    name: str
    baseline_zone_id: str
    planning_notes: str
    allowed_project_types: list[PlannerProjectType]


class PlanningSiteDefinition(BaseModel):
    site_id: str
    name: str
    state: str
    summary: str
    areas: list[PlanningAreaDefinition]
