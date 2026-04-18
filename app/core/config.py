from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Earth Twin Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    llm_explanations_enabled: bool = False
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "*")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def cors_origins(self) -> list[str]:
        normalized_value = self.cors_origins_raw.strip()
        if not normalized_value:
            return []
        if normalized_value == "*":
            return ["*"]
        return [origin.strip() for origin in normalized_value.split(",") if origin.strip()]

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

    @property
    def builder_sites_path(self) -> Path:
        return self.base_dir / "data" / "builder_sites.json"

    @property
    def builder_identities_path(self) -> Path:
        return self.base_dir / "data" / "builder_identities.json"


settings = Settings()
