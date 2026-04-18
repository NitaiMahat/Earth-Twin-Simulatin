from __future__ import annotations

from app.models.domain.zone import ZoneState
from app.repositories.zone_repository import zone_repository
from app.services.impact_service import impact_service


class ZoneService:
    def list_zones(self) -> list[ZoneState]:
        zones = zone_repository.list_zones()
        return [impact_service.normalize_zone(zone) for zone in zones]

    def get_zone(self, zone_id: str) -> ZoneState:
        zone = zone_repository.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Zone '{zone_id}' was not found.")
        return impact_service.normalize_zone(zone)

    def get_zone_detail(self, zone_id: str) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        return {
            "zone": zone,
            "risk_summary": impact_service.build_risk_summary(zone),
            "top_drivers": impact_service.build_top_drivers(zone),
            "recommended_focus": impact_service.build_zone_recommended_focus(zone),
        }


zone_service = ZoneService()
