from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    DEFORESTATION = "deforestation"
    TRAFFIC_INCREASE = "traffic_increase"
    POLLUTION_SPIKE = "pollution_spike"
    RESTORATION = "restoration"


class SimulationMode(str, Enum):
    PLANNING = "planning"
    LEARNING = "learning"


class AudienceType(str, Enum):
    PLANNER = "planner"
    MUNICIPALITY = "municipality"
    STUDENT = "student"
    EDUCATOR = "educator"
    GENERAL = "general"


class SimulationAction(BaseModel):
    zone_id: str
    action_type: ActionType
    intensity: float = Field(ge=0, le=1)
    duration_years: int = Field(ge=1, le=25)
