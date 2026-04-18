from __future__ import annotations

from fastapi import APIRouter

from app.models.api.responses import WorldResetResponse, WorldStateResponse
from app.services.world_service import world_service

router = APIRouter(prefix="/world", tags=["world"])


@router.get("", response_model=WorldStateResponse)
def get_world() -> WorldStateResponse:
    return WorldStateResponse(world=world_service.get_world())


@router.post("/reset", response_model=WorldResetResponse)
def reset_world() -> WorldResetResponse:
    return WorldResetResponse(
        message="World state reset from seed data.",
        world=world_service.reset_world(),
    )
