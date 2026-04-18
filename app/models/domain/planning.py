from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class PlannerProjectType(str, Enum):
    INDUSTRIAL_FACILITY = "industrial_facility"
    ROADWAY_LOGISTICS_EXPANSION = "roadway_logistics_expansion"
    MIXED_USE_REDEVELOPMENT = "mixed_use_redevelopment"


class InfrastructureCategory(str, Enum):
    ROAD = "road"
    BRIDGE = "bridge"
    BUILDINGS = "buildings"
    AIRPORT = "airport"
    GENERAL_AREA = "general_area"
    SOLAR_PANEL = "solar_panel"


class PlanningFieldType(str, Enum):
    NUMBER = "number"
    INTEGER = "integer"
    TEXT = "text"


class GeometrySelectionMode(str, Enum):
    LINE = "line"
    POLYGON = "polygon"


class MitigationCommitment(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanVerdict(str, Enum):
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    NOT_RECOMMENDED = "not_recommended"


class BuildFieldDefinition(BaseModel):
    field_name: str
    label: str
    field_type: PlanningFieldType
    unit: str | None = None
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    help_text: str


class GeometryPoint(BaseModel):
    latitude: float
    longitude: float


class MapToolDefinition(BaseModel):
    selection_mode: GeometrySelectionMode
    min_points: int
    max_points: int
    instructions: str
    auto_derived_fields: list[str]


class BuildSectionDefinition(BaseModel):
    infrastructure_type: InfrastructureCategory
    title: str
    summary: str
    default_project_type: PlannerProjectType
    fields: list[BuildFieldDefinition]
    map_tool: MapToolDefinition | None = None


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
