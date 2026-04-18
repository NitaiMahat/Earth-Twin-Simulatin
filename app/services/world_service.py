from __future__ import annotations

from app.models.domain.world import WorldState
from app.repositories.world_repository import world_repository
from app.services.impact_service import impact_service


class WorldService:
    def get_world(self) -> WorldState:
        world = world_repository.get_world()
        return impact_service.refresh_world(world)

    def reset_world(self) -> WorldState:
        world = world_repository.reset_world()
        return impact_service.refresh_world(world)


world_service = WorldService()
