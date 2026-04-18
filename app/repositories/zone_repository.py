from __future__ import annotations

from app.models.domain.zone import ZoneState
from app.repositories.world_repository import WorldRepository, world_repository


class ZoneRepository:
    def __init__(self, repository: WorldRepository) -> None:
        self.repository = repository

    def list_zones(self) -> list[ZoneState]:
        return self.repository.get_world().zones

    def get_zone(self, zone_id: str) -> ZoneState | None:
        for zone in self.repository.get_world().zones:
            if zone.zone_id == zone_id:
                return zone
        return None


zone_repository = ZoneRepository(world_repository)
