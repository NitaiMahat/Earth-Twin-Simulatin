from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.responses import ZoneDetailResponse, ZoneListResponse
from app.services.zone_service import zone_service

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=ZoneListResponse)
def list_zones() -> ZoneListResponse:
    zones = zone_service.list_zones()
    return ZoneListResponse(zones=zones, count=len(zones))


@router.get("/{zone_id}", response_model=ZoneDetailResponse)
def get_zone(zone_id: str) -> ZoneDetailResponse:
    try:
        zone_detail = zone_service.get_zone_detail(zone_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ZoneDetailResponse(**zone_detail)
