from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.domain.action import AudienceType, SimulationMode


class ScenarioTemplateAction(BaseModel):
    zone_id: str
    action_type: str
    intensity: float = Field(ge=0, le=1)
    duration_years: int = Field(ge=1, le=25)


class ScenarioTemplate(BaseModel):
    template_id: str
    name: str
    mode: SimulationMode
    description: str
    recommended_audience: AudienceType
    default_projection_years: int = Field(ge=1, le=50)
    default_actions: list[ScenarioTemplateAction]
    objective: str
    product_focus: str
    difficulty: str
