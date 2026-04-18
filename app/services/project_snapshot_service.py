from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.api.requests import SaveProjectReportRequest
from app.models.api.responses import (
    ProjectReportMetadataResponse,
    ProposalAssessmentResponse,
    SavedProjectDetailResponse,
    SavedProjectListResponse,
    SavedProjectSummaryResponse,
)
from app.models.domain.auth import AuthenticatedUser
from app.models.domain.planning import (
    GeometryPoint,
    InfrastructureCategory,
    MitigationCommitment,
    PlannerProjectType,
    PlanningLocationInput,
)
from app.repositories.project_snapshot_repository import ProjectSnapshotRepository
from app.services.planning_service import planning_service


class ProjectSnapshotService:
    def __init__(self) -> None:
        self._repository = ProjectSnapshotRepository(settings.database_connection_url)

    def _require_repository(self) -> ProjectSnapshotRepository:
        if self._repository.enabled and self._repository.ensure_ready():
            return self._repository
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project storage database is not configured or unavailable.",
        )

    def _report_response(self, payload: dict[str, object] | None) -> ProjectReportMetadataResponse:
        report_payload = payload or {}
        return ProjectReportMetadataResponse(
            ai_analysis=report_payload.get("ai_analysis") if isinstance(report_payload.get("ai_analysis"), str) else None,
            pdf_url=report_payload.get("pdf_url") if isinstance(report_payload.get("pdf_url"), str) else None,
            pdf_filename=report_payload.get("pdf_filename") if isinstance(report_payload.get("pdf_filename"), str) else None,
            updated_at=report_payload.get("updated_at") if isinstance(report_payload.get("updated_at"), str) else None,
        )

    def _summary_response(self, record: dict[str, object]) -> SavedProjectSummaryResponse:
        return SavedProjectSummaryResponse(
            project_id=str(record["project_id"]),
            project_name=str(record["project_name"]),
            created_at=str(record["created_at"]),
            updated_at=str(record["updated_at"]),
            continent_id=str(record["continent_id"]),
            project_type=PlannerProjectType(str(record["project_type"])),
            infrastructure_type=(
                InfrastructureCategory(str(record["infrastructure_type"]))
                if record.get("infrastructure_type")
                else None
            ),
            location_label=str(record["location_label"]),
            recommended_option=str(record["recommended_option"]),
            latest_report=self._report_response(record.get("latest_report_payload") if isinstance(record, dict) else {}),
        )

    def _detail_response(self, record: dict[str, object]) -> SavedProjectDetailResponse:
        return SavedProjectDetailResponse(
            project_id=str(record["project_id"]),
            project_name=str(record["project_name"]),
            created_at=str(record["created_at"]),
            updated_at=str(record["updated_at"]),
            assessment=ProposalAssessmentResponse.model_validate(record["assessment_payload"]),
            latest_report=self._report_response(record.get("latest_report_payload") if isinstance(record, dict) else {}),
        )

    def save_project(
        self,
        *,
        user: AuthenticatedUser,
        project_name: str,
        location: PlanningLocationInput,
        project_type: PlannerProjectType | None,
        infrastructure_type: InfrastructureCategory | None,
        geometry_points: list[GeometryPoint],
        infrastructure_details: dict[str, object],
        footprint_acres: float | None,
        estimated_daily_vehicle_trips: int | None,
        buildout_years: int | None,
        mitigation_commitment: MitigationCommitment,
        planner_notes: str | None,
    ) -> SavedProjectDetailResponse:
        repository = self._require_repository()
        assessment = planning_service.assess_proposal(
            location=location,
            project_type=project_type,
            infrastructure_type=infrastructure_type,
            geometry_points=geometry_points,
            infrastructure_details=infrastructure_details,
            footprint_acres=footprint_acres,
            estimated_daily_vehicle_trips=estimated_daily_vehicle_trips,
            buildout_years=buildout_years,
            mitigation_commitment=mitigation_commitment,
            planner_notes=planner_notes,
        )
        assessment_payload = assessment.model_dump(mode="json")
        record = repository.create_project(
            {
                "project_id": str(uuid4()),
                "user_id": user.user_id,
                "user_email": user.email,
                "project_name": project_name,
                "continent_id": assessment.continent_id,
                "project_type": assessment.project_type.value,
                "infrastructure_type": assessment.infrastructure_type.value if assessment.infrastructure_type else None,
                "location_label": assessment.location_context.label,
                "recommended_option": assessment.recommended_option,
                "assessment_payload": assessment_payload,
                "latest_report_payload": {},
            }
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to save the project snapshot.",
            )
        return self._detail_response(record)

    def list_projects(self, user: AuthenticatedUser) -> SavedProjectListResponse:
        repository = self._require_repository()
        records = repository.list_projects(user.user_id)
        projects = [self._summary_response(record) for record in records]
        return SavedProjectListResponse(projects=projects, count=len(projects))

    def get_project(self, user: AuthenticatedUser, project_id: str) -> SavedProjectDetailResponse:
        repository = self._require_repository()
        record = repository.get_project(user.user_id, project_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return self._detail_response(record)

    def update_report(
        self,
        user: AuthenticatedUser,
        project_id: str,
        payload: SaveProjectReportRequest,
    ) -> SavedProjectDetailResponse:
        repository = self._require_repository()
        report_payload = {
            "ai_analysis": payload.ai_analysis,
            "pdf_url": payload.pdf_url,
            "pdf_filename": payload.pdf_filename,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        record = repository.update_report(user.user_id, project_id, report_payload)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return self._detail_response(record)


project_snapshot_service = ProjectSnapshotService()
