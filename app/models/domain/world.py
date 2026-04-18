from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.domain.zone import ZoneState


class WorldState(BaseModel):
    world_id: str
    name: str
    baseline_mode: str = "dynamic_public"
    current_year: int = Field(ge=2000, le=2200)
    global_temperature: float
    global_co2_index: float
    sustainability_score: float = Field(default=0, ge=0, le=100)
    zones: list[ZoneState]
