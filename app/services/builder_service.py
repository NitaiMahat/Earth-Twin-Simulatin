from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.api.requests import BuilderProjectCreateRequest, BuilderProjectSimulateRequest
from app.models.api.responses import (
    BuilderIdentityResponse,
    BuilderManagedAreaResponse,
    BuilderManagedSiteAreaListResponse,
    BuilderManagedSiteResponse,
    BuilderProjectDetailResponse,
    BuilderProjectHistoryEntryResponse,
    BuilderProjectHistoryResponse,
    BuilderProjectListResponse,
    BuilderProjectReportResponse,
    BuilderProjectSummaryResponse,
    ProposalAssessmentResponse,
)
from app.models.domain.builder import (
    BuilderIdentity,
    BuilderManagedAreaDefinition,
    BuilderManagedSiteDefinition,
    BuilderProjectProposal,
    BuilderProjectRecord,
    BuilderProjectSnapshot,
    BuilderProjectStatus,
)
from app.repositories.builder_project_repository import builder_project_repository
from app.repositories.builder_site_repository import builder_site_repository
from app.services.planning_service import planning_service
from app.services.world_service import world_service


class BuilderService:
    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _get_site(self, site_id: str) -> BuilderManagedSiteDefinition:
        site = builder_site_repository.get_site(site_id)
        if site is None:
            raise ValueError(f"Builder site '{site_id}' was not found.")
        if site.country != "USA":
            raise ValueError(f"Builder site '{site_id}' is not eligible for USA-only builder planning.")
        return site

    def _get_area(self, site: BuilderManagedSiteDefinition, area_id: str) -> BuilderManagedAreaDefinition:
        for area in site.areas:
            if area.area_id == area_id:
                return area
        raise ValueError(f"Builder area '{area_id}' was not found in site '{site.site_id}'.")

    def _find_current_risk_level(self, baseline_zone_id: str) -> str:
        world = world_service.get_world()
        for zone in world.zones:
            if zone.zone_id == baseline_zone_id:
                return zone.risk_level.value
        raise ValueError(f"Zone '{baseline_zone_id}' was not found.")

    def _identity_response(self, identity: BuilderIdentity) -> BuilderIdentityResponse:
        return BuilderIdentityResponse(
            subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
            organization_id=identity.organization_id,
            role=identity.role,
        )

    def _proposal_from_request(self, request: BuilderProjectCreateRequest) -> BuilderProjectProposal:
        return BuilderProjectProposal(
            site_id=request.site_id,
            area_id=request.area_id,
            project_type=request.project_type,
            infrastructure_type=request.infrastructure_type,
            geometry_points=request.geometry_points,
            infrastructure_details=request.infrastructure_details,
            footprint_acres=request.footprint_acres,
            estimated_daily_vehicle_trips=request.estimated_daily_vehicle_trips,
            buildout_years=request.buildout_years,
            mitigation_commitment=request.mitigation_commitment,
            planner_notes=request.planner_notes,
        )

    def _ensure_project_access(self, identity: BuilderIdentity, project: BuilderProjectRecord) -> None:
        if identity.subject == project.owner_subject:
            return
        if identity.organization_id == project.organization_id:
            return
        raise PermissionError("You do not have access to this builder project.")

    def _summary_response(self, project: BuilderProjectRecord) -> BuilderProjectSummaryResponse:
        latest_recommendation = (
            project.latest_report_payload["recommended_option"]
            if project.latest_report_payload is not None
            else None
        )
        return BuilderProjectSummaryResponse(
            project_id=project.project_id,
            project_name=project.project_name,
            site_id=project.proposal.site_id,
            area_id=project.proposal.area_id,
            infrastructure_type=project.proposal.infrastructure_type,
            project_type=project.proposal.project_type,
            status=project.status,
            latest_recommendation=latest_recommendation,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _detail_response(self, project: BuilderProjectRecord) -> BuilderProjectDetailResponse:
        latest_report = (
            ProposalAssessmentResponse.model_validate(project.latest_report_payload)
            if project.latest_report_payload is not None
            else None
        )
        owner_identity = BuilderIdentity(
            token="",
            subject=project.owner_subject,
            email=project.owner_email,
            display_name=project.owner_email.split("@")[0],
            organization_id=project.organization_id,
            role="builder",
        )
        return BuilderProjectDetailResponse(
            project_id=project.project_id,
            project_name=project.project_name,
            owner=self._identity_response(owner_identity),
            site_id=project.proposal.site_id,
            area_id=project.proposal.area_id,
            status=project.status,
            proposal=project.proposal.model_dump(),
            latest_report=latest_report,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _report_response(self, project: BuilderProjectRecord) -> BuilderProjectReportResponse:
        if project.latest_report_payload is None:
            raise ValueError(f"Builder project '{project.project_id}' has no report yet.")
        return BuilderProjectReportResponse(
            project_id=project.project_id,
            project_name=project.project_name,
            report=ProposalAssessmentResponse.model_validate(project.latest_report_payload),
            last_updated_at=project.updated_at,
        )

    def _history_response(self, project: BuilderProjectRecord) -> BuilderProjectHistoryResponse:
        return BuilderProjectHistoryResponse(
            project_id=project.project_id,
            project_name=project.project_name,
            entries=[
                BuilderProjectHistoryEntryResponse(
                    snapshot_id=entry.snapshot_id,
                    created_at=entry.created_at,
                    recommended_option=entry.report_payload["recommended_option"],
                    report=ProposalAssessmentResponse.model_validate(entry.report_payload),
                )
                for entry in reversed(project.history)
            ],
            count=len(project.history),
        )

    def list_sites(self) -> list[BuilderManagedSiteResponse]:
        sites = []
        for site in builder_site_repository.list_sites():
            if site.country != "USA":
                continue
            sites.append(
                BuilderManagedSiteResponse(
                    site_id=site.site_id,
                    name=site.name,
                    country=site.country,
                    state=site.state,
                    summary=site.summary,
                    area_count=len(site.areas),
                )
            )
        return sites

    def get_site_areas(self, site_id: str) -> BuilderManagedSiteAreaListResponse:
        site = self._get_site(site_id)
        return BuilderManagedSiteAreaListResponse(
            site_id=site.site_id,
            name=site.name,
            country=site.country,
            state=site.state,
            summary=site.summary,
            areas=[
                BuilderManagedAreaResponse(
                    area_id=area.area_id,
                    name=area.name,
                    baseline_zone_id=area.baseline_zone_id,
                    current_risk_level=self._find_current_risk_level(area.baseline_zone_id),
                    planning_notes=area.planning_notes,
                    allowed_project_types=area.allowed_project_types,
                )
                for area in site.areas
            ],
        )

    def create_project(
        self,
        identity: BuilderIdentity,
        request: BuilderProjectCreateRequest,
    ) -> BuilderProjectDetailResponse:
        site = self._get_site(request.site_id)
        self._get_area(site, request.area_id)
        proposal = self._proposal_from_request(request)
        now = self._now()
        project = BuilderProjectRecord(
            project_id=f"builder_project_{uuid4().hex[:12]}",
            project_name=request.project_name,
            owner_subject=identity.subject,
            owner_email=identity.email,
            organization_id=identity.organization_id,
            proposal=proposal,
            created_at=now,
            updated_at=now,
        )
        builder_project_repository.save_project(project)
        return self._detail_response(project)

    def list_projects(self, identity: BuilderIdentity) -> BuilderProjectListResponse:
        projects = [
            self._summary_response(project)
            for project in builder_project_repository.list_projects()
            if project.organization_id == identity.organization_id or project.owner_subject == identity.subject
        ]
        projects.sort(key=lambda project: project.updated_at, reverse=True)
        return BuilderProjectListResponse(projects=projects, count=len(projects))

    def get_project(self, identity: BuilderIdentity, project_id: str) -> BuilderProjectDetailResponse:
        project = builder_project_repository.get_project(project_id)
        if project is None:
            raise ValueError(f"Builder project '{project_id}' was not found.")
        self._ensure_project_access(identity, project)
        return self._detail_response(project)

    def simulate_project(
        self,
        identity: BuilderIdentity,
        project_id: str,
        overrides: BuilderProjectSimulateRequest | None = None,
    ) -> BuilderProjectReportResponse:
        project = builder_project_repository.get_project(project_id)
        if project is None:
            raise ValueError(f"Builder project '{project_id}' was not found.")
        self._ensure_project_access(identity, project)

        site = self._get_site(project.proposal.site_id)
        current_proposal = project.proposal.model_copy(deep=True)
        if overrides is not None:
            if overrides.project_name:
                project.project_name = overrides.project_name
            if overrides.mitigation_commitment is not None:
                current_proposal.mitigation_commitment = overrides.mitigation_commitment
                project.proposal.mitigation_commitment = overrides.mitigation_commitment
            if overrides.planner_notes is not None:
                current_proposal.planner_notes = overrides.planner_notes
                project.proposal.planner_notes = overrides.planner_notes

        report = planning_service.assess_proposal(
            site_id=site.planning_site_id,
            area_id=current_proposal.area_id,
            project_type=current_proposal.project_type,
            infrastructure_type=current_proposal.infrastructure_type,
            geometry_points=current_proposal.geometry_points,
            infrastructure_details=current_proposal.infrastructure_details,
            footprint_acres=current_proposal.footprint_acres,
            estimated_daily_vehicle_trips=current_proposal.estimated_daily_vehicle_trips,
            buildout_years=current_proposal.buildout_years,
            mitigation_commitment=current_proposal.mitigation_commitment,
            planner_notes=current_proposal.planner_notes,
        )

        now = self._now()
        snapshot = BuilderProjectSnapshot(
            snapshot_id=f"builder_snapshot_{uuid4().hex[:12]}",
            created_at=now,
            report_payload=report.model_dump(),
        )
        project.history.append(snapshot)
        project.status = BuilderProjectStatus.SIMULATED
        project.latest_report_payload = report.model_dump()
        project.latest_snapshot_id = snapshot.snapshot_id
        project.updated_at = now
        builder_project_repository.save_project(project)

        return self._report_response(project)

    def get_project_report(self, identity: BuilderIdentity, project_id: str) -> BuilderProjectReportResponse:
        project = builder_project_repository.get_project(project_id)
        if project is None:
            raise ValueError(f"Builder project '{project_id}' was not found.")
        self._ensure_project_access(identity, project)
        return self._report_response(project)

    def get_project_history(self, identity: BuilderIdentity, project_id: str) -> BuilderProjectHistoryResponse:
        project = builder_project_repository.get_project(project_id)
        if project is None:
            raise ValueError(f"Builder project '{project_id}' was not found.")
        self._ensure_project_access(identity, project)
        return self._history_response(project)


builder_service = BuilderService()
