from __future__ import annotations

from pydantic import BaseModel


class ContinentDefinition(BaseModel):
    continent_id: str
    zone_id: str
    name: str
    latitude: float
    longitude: float
    representative_country_code: str | None = None
    summary: str
