from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.builder_auth import require_builder_identity
from app.models.api.requests import BuilderProjectCreateRequest, BuilderProjectSimulateRequest
from app.models.api.responses import (
    BuilderManagedSiteAreaListResponse,
    BuilderManagedSiteResponse,
    BuilderProjectDetailResponse,
    BuilderProjectHistoryResponse,
    BuilderProjectListResponse,
    BuilderProjectReportResponse,
)
from app.models.domain.builder import BuilderIdentity
from app.services.builder_service import builder_service

router = APIRouter(prefix="/builders", tags=["builders"])


@router.get("/sites", response_model=list[BuilderManagedSiteResponse])
def list_builder_sites(
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> list[BuilderManagedSiteResponse]:
    return builder_service.list_sites()


@router.get("/sites/{site_id}/areas", response_model=BuilderManagedSiteAreaListResponse)
def get_builder_site_areas(
    site_id: str,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderManagedSiteAreaListResponse:
    try:
        return builder_service.get_site_areas(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects", response_model=BuilderProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_builder_project(
    payload: BuilderProjectCreateRequest,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectDetailResponse:
    try:
        return builder_service.create_project(identity, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/projects", response_model=BuilderProjectListResponse)
def list_builder_projects(
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectListResponse:
    return builder_service.list_projects(identity)


@router.get("/projects/{project_id}", response_model=BuilderProjectDetailResponse)
def get_builder_project(
    project_id: str,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectDetailResponse:
    try:
        return builder_service.get_project(identity, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/projects/{project_id}/simulate", response_model=BuilderProjectReportResponse)
def simulate_builder_project(
    project_id: str,
    payload: BuilderProjectSimulateRequest | None = None,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectReportResponse:
    try:
        return builder_service.simulate_project(identity, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/projects/{project_id}/report", response_model=BuilderProjectReportResponse)
def get_builder_project_report(
    project_id: str,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectReportResponse:
    try:
        return builder_service.get_project_report(identity, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/projects/{project_id}/history", response_model=BuilderProjectHistoryResponse)
def get_builder_project_history(
    project_id: str,
    identity: BuilderIdentity = Depends(require_builder_identity),
) -> BuilderProjectHistoryResponse:
    try:
        return builder_service.get_project_history(identity, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
