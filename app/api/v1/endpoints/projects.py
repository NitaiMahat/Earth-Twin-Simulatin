from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps.supabase_auth import get_current_user
from app.models.api.requests import SaveProjectReportRequest, SaveProjectRequest
from app.models.api.responses import SavedProjectDetailResponse, SavedProjectListResponse
from app.models.domain.auth import AuthenticatedUser
from app.services.project_snapshot_service import project_snapshot_service

router = APIRouter(prefix="/my-projects", tags=["projects"])


@router.get("", response_model=SavedProjectListResponse)
def list_my_projects(user: AuthenticatedUser = Depends(get_current_user)) -> SavedProjectListResponse:
    return project_snapshot_service.list_projects(user)


@router.post("", response_model=SavedProjectDetailResponse)
def save_project_snapshot(
    payload: SaveProjectRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedProjectDetailResponse:
    return project_snapshot_service.save_project(
        user=user,
        project_name=payload.project_name,
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
        text_planning=payload.text_planning.model_dump(mode="json") if payload.text_planning is not None else None,
    )


@router.get("/{project_id}", response_model=SavedProjectDetailResponse)
def get_project_snapshot(
    project_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedProjectDetailResponse:
    return project_snapshot_service.get_project(user, project_id)


@router.patch("/{project_id}/report", response_model=SavedProjectDetailResponse)
def update_project_report(
    project_id: str,
    payload: SaveProjectReportRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedProjectDetailResponse:
    return project_snapshot_service.update_report(user, project_id, payload)


@router.post("/{project_id}/report/generate", response_model=SavedProjectDetailResponse)
def generate_project_report(
    project_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedProjectDetailResponse:
    return project_snapshot_service.generate_and_store_report(user, project_id)
