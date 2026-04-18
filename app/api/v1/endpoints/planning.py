from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import (
    GeometryResolutionRequest,
    ProposalAssessmentRequest,
    TextPlanningDraftRequest,
    TextPlanningRunRequest,
)
from app.models.api.responses import (
    GeometryResolutionResponse,
    PlanningBuildOptionsResponse,
    PlanningSiteResponse,
    ProposalAssessmentResponse,
    TextPlanningExtractionResponse,
    TextPlanningRunResponse,
)
from app.services.planning_service import planning_service
from app.services.text_planning_service import text_planning_service

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
            location=payload.location,
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
            location=payload.location,
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


@router.post("/text/draft", response_model=TextPlanningExtractionResponse)
def draft_text_plan(payload: TextPlanningDraftRequest) -> TextPlanningExtractionResponse:
    try:
        return text_planning_service.draft_from_text(
            location=payload.location,
            geometry_points=payload.geometry_points,
            user_prompt=payload.user_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/text/run", response_model=TextPlanningRunResponse)
def run_text_plan(payload: TextPlanningRunRequest) -> TextPlanningRunResponse:
    try:
        return text_planning_service.run_from_text(
            location=payload.location,
            geometry_points=payload.geometry_points,
            user_prompt=payload.user_prompt,
            mitigation_commitment=payload.mitigation_commitment,
            confirmed_overrides=payload.confirmed_overrides,
            planner_notes=payload.planner_notes,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
