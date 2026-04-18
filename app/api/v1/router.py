from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.builders import router as builders_router
from app.api.v1.endpoints.education import router as education_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.planning import router as planning_router
from app.api.v1.endpoints.scenarios import router as scenarios_router
from app.api.v1.endpoints.simulation import router as simulation_router
from app.api.v1.endpoints.world import router as world_router
from app.api.v1.endpoints.zones import router as zones_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(world_router)
api_router.include_router(zones_router)
api_router.include_router(simulation_router)
api_router.include_router(scenarios_router)
api_router.include_router(ai_router)
api_router.include_router(planning_router)
api_router.include_router(education_router)
api_router.include_router(builders_router)
