from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Earth Twin Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    llm_explanations_enabled: bool = False

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def seed_world_path(self) -> Path:
        return self.base_dir / "data" / "seed_world.json"

    @property
    def scenario_templates_path(self) -> Path:
        return self.base_dir / "data" / "scenario_templates.json"

    @property
    def planning_site_path(self) -> Path:
        return self.base_dir / "data" / "planning_site.json"


settings = Settings()
