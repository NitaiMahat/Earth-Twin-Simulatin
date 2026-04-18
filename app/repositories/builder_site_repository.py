from __future__ import annotations

import json

from app.core.config import settings
from app.models.domain.builder import BuilderManagedSiteDefinition


class BuilderSiteRepository:
    def __init__(self) -> None:
        self._sites = self._load_sites()

    def _load_sites(self) -> list[BuilderManagedSiteDefinition]:
        with settings.builder_sites_path.open("r", encoding="utf-8") as site_file:
            payload = json.load(site_file)
        return [BuilderManagedSiteDefinition.model_validate(item) for item in payload]

    def list_sites(self) -> list[BuilderManagedSiteDefinition]:
        return self._sites

    def get_site(self, site_id: str) -> BuilderManagedSiteDefinition | None:
        for site in self._sites:
            if site.site_id == site_id:
                return site
        return None


builder_site_repository = BuilderSiteRepository()
