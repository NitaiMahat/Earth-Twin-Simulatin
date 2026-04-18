from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import GeometryResolutionRequest, ProposalAssessmentRequest
from app.models.api.responses import (
    GeometryResolutionResponse,
    PlanningBuildOptionsResponse,
    PlanningSiteResponse,
    ProposalAssessmentResponse,
)
from app.services.planning_service import planning_service

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/site", response_model=PlanningSiteResponse)
def get_planning_site() -> PlanningSiteResponse:
    return planning_service.get_site()


@router.get("/build-options", response_model=PlanningBuildOptionsResponse)
def get_build_options() -> PlanningBuildOptionsResponse:
    return planning_service.get_build_options()


@router.post("/geometry/resolve", response_model=GeometryResolutionResponse)
def resolve_geometry(payload: GeometryResolutionRequest) -> GeometryResolutionResponse:
    try:
        return planning_service.resolve_geometry(
            site_id=payload.site_id,
            area_id=payload.area_id,
            infrastructure_type=payload.infrastructure_type,
            geometry_points=payload.geometry_points,
            infrastructure_details=payload.infrastructure_details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/proposals/assess", response_model=ProposalAssessmentResponse)
def assess_proposal(payload: ProposalAssessmentRequest) -> ProposalAssessmentResponse:
    try:
        return planning_service.assess_proposal(
            site_id=payload.site_id,
            area_id=payload.area_id,
            project_type=payload.project_type,
            infrastructure_type=payload.infrastructure_type,
            geometry_points=payload.geometry_points,
            infrastructure_details=payload.infrastructure_details,
            footprint_acres=payload.footprint_acres,
            estimated_daily_vehicle_trips=payload.estimated_daily_vehicle_trips,
            buildout_years=payload.buildout_years,
            mitigation_commitment=payload.mitigation_commitment,
            planner_notes=payload.planner_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
