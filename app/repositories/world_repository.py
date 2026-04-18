from __future__ import annotations

import json

from app.core.config import settings
from app.models.domain.world import WorldState


class WorldRepository:
    def __init__(self) -> None:
        self._world = self._load_seed_world()

    def _load_seed_world(self) -> WorldState:
        with settings.seed_world_path.open("r", encoding="utf-8") as seed_file:
            payload = json.load(seed_file)
        return WorldState.model_validate(payload)

    def get_world(self) -> WorldState:
        return self._world

    def save_world(self, world: WorldState) -> WorldState:
        self._world = world
        return self._world

    def reset_world(self) -> WorldState:
        self._world = self._load_seed_world()
        return self._world


world_repository = WorldRepository()
