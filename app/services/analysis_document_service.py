from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.api.responses import (
    AnalysisMetricCardResponse,
    AnalysisSectionResponse,
    ProjectAnalysisDocumentResponse,
)
from app.models.domain.planning import InfrastructureCategory, PlannerProjectType
from app.models.domain.simulation import ProjectionSimulationResult
from app.models.domain.zone import ZoneState
from app.services.gemini_service import gemini_service


class AnalysisDocumentService:
    def _project_label(
        self,
        infrastructure_type: InfrastructureCategory | None,
        project_type: PlannerProjectType,
    ) -> str:
        if infrastructure_type is not None:
            return infrastructure_type.value.replace("_", " ")
        return project_type.value.replace("_", " ")

    def _find_target_zone(self, projection: ProjectionSimulationResult, zone_id: str) -> ZoneState:
        for zone in projection.projected_world.zones:
            if zone.zone_id == zone_id:
                return zone
        return projection.projected_world.zones[0]

    def _metric_cards(
        self,
        baseline_zone: ZoneState,
        submitted_zone: ZoneState,
        mitigated_zone: ZoneState,
        submitted_score: float,
        mitigated_score: float,
    ) -> list[AnalysisMetricCardResponse]:
        return [
            AnalysisMetricCardResponse(
                label="Sustainability Score",
                baseline_value=round(baseline_zone.sustainability_score, 2),
                submitted_value=round(submitted_score, 2),
                mitigated_value=round(mitigated_score, 2),
            ),
            AnalysisMetricCardResponse(
                label="Pollution Level",
                baseline_value=round(baseline_zone.pollution_level, 2),
                submitted_value=round(submitted_zone.pollution_level, 2),
                mitigated_value=round(mitigated_zone.pollution_level, 2),
                lower_is_better=True,
            ),
            AnalysisMetricCardResponse(
                label="Traffic Level",
                baseline_value=round(baseline_zone.traffic_level, 2),
                submitted_value=round(submitted_zone.traffic_level, 2),
                mitigated_value=round(mitigated_zone.traffic_level, 2),
                lower_is_better=True,
            ),
            AnalysisMetricCardResponse(
                label="Ecosystem Health",
                baseline_value=round(baseline_zone.ecosystem_health, 2),
                submitted_value=round(submitted_zone.ecosystem_health, 2),
                mitigated_value=round(mitigated_zone.ecosystem_health, 2),
            ),
            AnalysisMetricCardResponse(
                label="Temperature",
                unit="C",
                baseline_value=round(baseline_zone.temperature, 2),
                submitted_value=round(submitted_zone.temperature, 2),
                mitigated_value=round(mitigated_zone.temperature, 2),
                lower_is_better=True,
            ),
        ]

    def _fallback_ai_analysis(
        self,
        *,
        project_label: str,
        location_label: str,
        recommended_option: str,
        submitted_projection: ProjectionSimulationResult,
        mitigated_projection: ProjectionSimulationResult,
    ) -> str:
        better_projection = (
            mitigated_projection if recommended_option == "mitigated_plan" else submitted_projection
        )
        return (
            "EXECUTIVE SUMMARY\n"
            f"The {project_label} simulation for {location_label} indicates the {recommended_option.replace('_', ' ')} "
            f"is the stronger path with an overall outlook of {better_projection.overall_outlook}.\n\n"
            "KEY FINDINGS\n"
            f"* Submitted score: {submitted_projection.sustainability_score:.1f}\n"
            f"* Mitigated score: {mitigated_projection.sustainability_score:.1f}\n"
            f"* Recommended option: {recommended_option}\n"
            "* Public baseline conditions were used before applying scenario rules.\n\n"
            "IMPROVEMENT RECOMMENDATIONS\n"
            "1. Prioritize the mitigations tied to the highest-risk drivers.\n"
            "2. Revisit traffic and pollution assumptions before final approval.\n"
            "3. Keep monitoring the site after implementation.\n"
            "4. Save the project snapshot for later comparison.\n\n"
            "LONG-TERM OUTLOOK\n"
            "If the stronger option is maintained, the project is positioned to reduce downside risk relative to the base proposal."
        )

    def _parse_sections(self, ai_analysis: str) -> AnalysisSectionResponse:
        headers = {
            "EXECUTIVE SUMMARY": "executive_summary",
            "KEY FINDINGS": "key_findings",
            "IMPROVEMENT RECOMMENDATIONS": "improvement_recommendations",
            "LONG-TERM OUTLOOK": "long_term_outlook",
        }
        bucket: dict[str, list[str]] = {value: [] for value in headers.values()}
        current: str | None = None
        for line in ai_analysis.splitlines():
            stripped = line.strip()
            if stripped in headers:
                current = headers[stripped]
                continue
            if current and stripped:
                bucket[current].append(stripped.lstrip("*-0123456789.) ").strip())

        executive_summary = " ".join(bucket["executive_summary"]).strip()
        key_findings = [item for item in bucket["key_findings"] if item]
        recommendations = [item for item in bucket["improvement_recommendations"] if item]
        long_term_outlook = " ".join(bucket["long_term_outlook"]).strip()

        return AnalysisSectionResponse(
            executive_summary=executive_summary or "Simulation completed successfully.",
            key_findings=key_findings[:4] or ["Scenario comparison completed with baseline and mitigated outcomes."],
            improvement_recommendations=recommendations[:4] or ["Review the recommended mitigation bundle before saving the project."],
            long_term_outlook=long_term_outlook or "Long-term outlook depends on implementation quality and sustained mitigation.",
        )

    def build_document(
        self,
        *,
        location_label: str,
        planner_notes: str | None,
        infrastructure_type: InfrastructureCategory | None,
        project_type: PlannerProjectType,
        baseline_zone: ZoneState,
        baseline_zone_id: str,
        submitted_projection: ProjectionSimulationResult,
        mitigated_projection: ProjectionSimulationResult,
        submitted_actions: list[dict[str, object]],
        mitigated_actions: list[dict[str, object]],
        submitted_top_risks: list[str],
        mitigated_top_risks: list[str],
        recommended_option: str,
    ) -> ProjectAnalysisDocumentResponse:
        submitted_zone = self._find_target_zone(submitted_projection, baseline_zone_id)
        mitigated_zone = self._find_target_zone(mitigated_projection, baseline_zone_id)
        project_label = self._project_label(infrastructure_type, project_type)
        goal = planner_notes or f"Evaluate a {project_label} project in {location_label}"

        recommended_projection = mitigated_projection if recommended_option == "mitigated_plan" else submitted_projection
        recommended_actions = mitigated_actions if recommended_option == "mitigated_plan" else submitted_actions
        recommended_zone = mitigated_zone if recommended_option == "mitigated_plan" else submitted_zone

        try:
            ai_analysis = gemini_service.suggest_improvements(
                goal=goal,
                zone_name=location_label,
                actions=recommended_actions,
                initial_metrics=baseline_zone.model_dump(mode="json"),
                final_metrics=recommended_zone.model_dump(mode="json"),
                projection_years=5,
                sustainability_score=recommended_projection.sustainability_score,
                overall_outlook=recommended_projection.overall_outlook,
            )
        except (ValueError, RuntimeError):
            ai_analysis = self._fallback_ai_analysis(
                project_label=project_label,
                location_label=location_label,
                recommended_option=recommended_option,
                submitted_projection=submitted_projection,
                mitigated_projection=mitigated_projection,
            )

        sections = self._parse_sections(ai_analysis)
        summary = (
            f"{location_label} {project_label} simulation completed. "
            f"The {recommended_option.replace('_', ' ')} is currently favored based on the scenario comparison."
        )

        return ProjectAnalysisDocumentResponse(
            title=f"{location_label} {project_label.title()} Analysis",
            simulated_project_summary=goal,
            summary=summary,
            recommended_option=recommended_option,
            generated_at=datetime.now(UTC).isoformat(),
            metric_cards=self._metric_cards(
                baseline_zone,
                submitted_zone,
                mitigated_zone,
                submitted_projection.sustainability_score,
                mitigated_projection.sustainability_score,
            ),
            submitted_top_risks=submitted_top_risks[:4],
            mitigated_top_risks=mitigated_top_risks[:4],
            ai_analysis=ai_analysis,
            sections=sections,
        )


analysis_document_service = AnalysisDocumentService()
