from __future__ import annotations

from app.models.domain.world import WorldState
from app.services.public_baseline_service import public_baseline_service


class WorldRepository:
    def __init__(self) -> None:
        self._world = self._load_world()

    def _load_world(self) -> WorldState:
        return public_baseline_service.build_world()

    def get_world(self) -> WorldState:
        return self._world

    def save_world(self, world: WorldState) -> WorldState:
        self._world = world
        return self._world

    def reset_world(self) -> WorldState:
        self._world = self._load_world()
        return self._world


world_repository = WorldRepository()
