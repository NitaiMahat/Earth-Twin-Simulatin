from __future__ import annotations

import json

from app.core.config import settings
from app.core.constants import RiskLevel
from app.models.api.responses import (
    PlanScorecardResponse,
    PlannerSimulationActionResponse,
    PlannerSimulationInputsResponse,
    PlanningAreaResponse,
    PlanningSiteResponse,
    ProposalAssessmentResponse,
)
from app.models.domain.action import SimulationAction, SimulationMode
from app.models.domain.planning import (
    MitigationCommitment,
    PlanningAreaDefinition,
    PlanningSiteDefinition,
    PlanVerdict,
    PlannerProjectType,
)
from app.models.domain.simulation import ProjectionSimulationResult
from app.models.domain.zone import ZoneState
from app.services.action_mapper import action_mapper
from app.services.impact_service import impact_service
from app.services.simulation_engine import simulation_engine
from app.services.world_service import world_service


SITE_ID = "illinois_calumet_corridor_demo"
DEFAULT_PROJECTION_YEARS = 5
SUBMITTED_SCENARIO_NAME = "Submitted Plan"
MITIGATED_SCENARIO_NAME = "Mitigated Plan"

RESTORATION_ACTION_BY_AREA = {
    "calumet_industrial_strip": "add_urban_park",
    "arterial_infill_corridor": "improve_public_transit",
    "river_buffer_redevelopment": "restoration_corridor",
}

PROJECT_ACTION_MAPPING = {
    PlannerProjectType.INDUSTRIAL_FACILITY: ("industrial_expansion", "expand_roadway"),
    PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION: ("expand_roadway", "industrial_expansion"),
    PlannerProjectType.MIXED_USE_REDEVELOPMENT: ("expand_roadway", "reduce_green_space"),
}

ACTION_LABELS = {
    "industrial_expansion": "industrial emissions controls and cleaner operations",
    "expand_roadway": "trip reduction and freight demand management",
    "reduce_green_space": "tree replacement, open-space protection, and shade requirements",
    "add_urban_park": "urban park and green buffer investment",
    "improve_public_transit": "public transit access and mode-shift commitments",
    "restoration_corridor": "river-edge habitat restoration and buffer protections",
}

TOP_RISK_MITIGATIONS = {
    "high pollution": "Require emissions controls and pollution monitoring before approval.",
    "high traffic": "Require trip reduction and freight/transit management measures.",
    "low tree cover": "Require tree replacement, shade cover, and green buffer restoration.",
    "low biodiversity": "Require habitat restoration and construction-phase ecological protections.",
    "low ecosystem health": "Require phased restoration before major site disturbance.",
    "high temperature": "Require cooling surfaces, shade, and heat mitigation features.",
}


class PlanningService:
    def __init__(self) -> None:
        self._site = self._load_site()

    def _load_site(self) -> PlanningSiteDefinition:
        with settings.planning_site_path.open("r", encoding="utf-8") as planning_file:
            payload = json.load(planning_file)
        return PlanningSiteDefinition.model_validate(payload)

    def _get_area(self, area_id: str) -> PlanningAreaDefinition:
        for area in self._site.areas:
            if area.area_id == area_id:
                return area
        raise ValueError(f"Unknown area_id '{area_id}'.")

    def _validate_site(self, site_id: str) -> None:
        if site_id != self._site.site_id:
            raise ValueError(f"Unknown site_id '{site_id}'. Expected '{self._site.site_id}'.")

    def _validate_project_type(self, area: PlanningAreaDefinition, project_type: PlannerProjectType) -> None:
        if project_type not in area.allowed_project_types:
            allowed_types = ", ".join(project_type.value for project_type in area.allowed_project_types)
            raise ValueError(
                f"Project type '{project_type.value}' is not allowed for area '{area.area_id}'. "
                f"Allowed values: {allowed_types}."
            )

    def _find_zone(self, zone_id: str) -> ZoneState:
        world = world_service.get_world()
        for zone in world.zones:
            if zone.zone_id == zone_id:
                return zone
        raise ValueError(f"Zone '{zone_id}' was not found.")

    def get_site(self) -> PlanningSiteResponse:
        areas = []
        for area in self._site.areas:
            zone = self._find_zone(area.baseline_zone_id)
            areas.append(
                PlanningAreaResponse(
                    area_id=area.area_id,
                    name=area.name,
                    baseline_zone_id=area.baseline_zone_id,
                    current_risk_level=zone.risk_level.value,
                    planning_notes=area.planning_notes,
                    allowed_project_types=area.allowed_project_types,
                )
            )

        return PlanningSiteResponse(
            site_id=self._site.site_id,
            name=self._site.name,
            state=self._site.state,
            summary=self._site.summary,
            areas=areas,
        )

    def _bucket_footprint(self, footprint_acres: float) -> tuple[str, float]:
        if footprint_acres < 10:
            return "small", 0.3
        if footprint_acres <= 40:
            return "medium", 0.6
        return "large", 0.85

    def _bucket_traffic(self, estimated_daily_vehicle_trips: int) -> tuple[str, float]:
        if estimated_daily_vehicle_trips < 500:
            return "low", 0.3
        if estimated_daily_vehicle_trips <= 2000:
            return "medium", 0.6
        return "high", 0.85

    def _dedupe_actions(self, actions: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: dict[tuple[str, str], dict[str, object]] = {}

        for action in actions:
            key = (str(action["zone_id"]), str(action["requested_action_type"]))
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = action
                continue

            existing["intensity"] = max(float(existing["intensity"]), float(action["intensity"]))
            existing["duration_years"] = max(int(existing["duration_years"]), int(action["duration_years"]))

        return list(deduped.values())

    def _build_actions(
        self,
        area: PlanningAreaDefinition,
        project_type: PlannerProjectType,
        buildout_years: int,
        footprint_intensity: float,
        traffic_intensity: float,
        mitigation_commitment: MitigationCommitment,
    ) -> list[dict[str, object]]:
        primary_action, secondary_action = PROJECT_ACTION_MAPPING[project_type]
        actions: list[dict[str, object]] = [
            {
                "zone_id": area.baseline_zone_id,
                "requested_action_type": primary_action,
                "intensity": footprint_intensity,
                "duration_years": buildout_years,
            },
            {
                "zone_id": area.baseline_zone_id,
                "requested_action_type": secondary_action,
                "intensity": traffic_intensity,
                "duration_years": buildout_years,
            },
        ]

        restoration_action = RESTORATION_ACTION_BY_AREA[area.area_id]
        mitigation_duration = min(buildout_years, DEFAULT_PROJECTION_YEARS)

        if mitigation_commitment in {MitigationCommitment.MEDIUM, MitigationCommitment.HIGH}:
            actions.append(
                {
                    "zone_id": area.baseline_zone_id,
                    "requested_action_type": restoration_action,
                    "intensity": 0.6 if mitigation_commitment == MitigationCommitment.MEDIUM else 0.85,
                    "duration_years": mitigation_duration,
                }
            )

        if mitigation_commitment == MitigationCommitment.HIGH:
            actions.append(
                {
                    "zone_id": area.baseline_zone_id,
                    "requested_action_type": "improve_public_transit",
                    "intensity": 0.6,
                    "duration_years": mitigation_duration,
                }
            )

        return self._dedupe_actions(actions)

    def _normalize_actions(self, actions: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[SimulationAction]]:
        normalized_actions: list[dict[str, object]] = []
        simulation_actions: list[SimulationAction] = []

        for action in actions:
            requested_action_type = str(action["requested_action_type"])
            normalized_action_type = action_mapper.normalize_action_type(requested_action_type).value
            normalized_action = {
                "zone_id": str(action["zone_id"]),
                "requested_action_type": requested_action_type,
                "normalized_action_type": normalized_action_type,
                "intensity": round(float(action["intensity"]), 2),
                "duration_years": int(action["duration_years"]),
            }
            normalized_actions.append(normalized_action)
            simulation_actions.append(
                SimulationAction(
                    zone_id=normalized_action["zone_id"],
                    action_type=action_mapper.normalize_action_type(requested_action_type),
                    intensity=normalized_action["intensity"],
                    duration_years=normalized_action["duration_years"],
                )
            )

        return normalized_actions, simulation_actions

    def _resolve_verdict(self, projection: ProjectionSimulationResult) -> PlanVerdict:
        has_critical_zone = any(zone.risk_level == RiskLevel.CRITICAL for zone in projection.projected_world.zones)
        if projection.overall_outlook == "negative" or has_critical_zone:
            return PlanVerdict.NOT_RECOMMENDED
        if projection.overall_outlook == "mixed":
            return PlanVerdict.CONDITIONAL
        return PlanVerdict.RECOMMENDED

    def _build_required_mitigations(
        self,
        area: PlanningAreaDefinition,
        projection: ProjectionSimulationResult,
        action_inputs: list[dict[str, object]],
    ) -> list[str]:
        required_mitigations: list[str] = []
        action_types = {str(action["requested_action_type"]) for action in action_inputs}

        highest_risk_zone = projection.highest_risk_zone
        if highest_risk_zone is not None:
            for driver_name in impact_service.get_top_driver_names(highest_risk_zone):
                mitigation = TOP_RISK_MITIGATIONS.get(driver_name)
                if mitigation and mitigation not in required_mitigations:
                    required_mitigations.append(mitigation)

        restoration_action = RESTORATION_ACTION_BY_AREA[area.area_id]
        if restoration_action not in action_types:
            required_mitigations.append(f"Add {ACTION_LABELS[restoration_action]} as a condition of approval.")
        if "improve_public_transit" not in action_types:
            required_mitigations.append("Add public transit access and trip-shift measures before approval.")

        if not required_mitigations:
            required_mitigations.append(
                "Maintain the proposed mitigation bundle and monitor the highest-risk parcel during delivery."
            )

        return required_mitigations[:4]

    def _build_scorecard(
        self,
        area: PlanningAreaDefinition,
        projection: ProjectionSimulationResult,
        action_inputs: list[dict[str, object]],
    ) -> PlanScorecardResponse:
        return PlanScorecardResponse(
            plan_score=round(projection.sustainability_score, 2),
            verdict=self._resolve_verdict(projection),
            overall_outlook=projection.overall_outlook,
            highest_risk_zone=impact_service.build_compact_zone_summary(projection.highest_risk_zone),
            top_risks=projection.highest_risk_zone_top_drivers or ["No concentrated high-risk drivers were detected."],
            required_mitigations=self._build_required_mitigations(area, projection, action_inputs),
            summary_text=projection.summary_text,
        )

    def assess_proposal(
        self,
        site_id: str,
        area_id: str,
        project_type: PlannerProjectType,
        footprint_acres: float,
        estimated_daily_vehicle_trips: int,
        buildout_years: int,
        mitigation_commitment: MitigationCommitment,
        planner_notes: str | None = None,
    ) -> ProposalAssessmentResponse:
        self._validate_site(site_id)
        area = self._get_area(area_id)
        self._validate_project_type(area, project_type)

        world = world_service.get_world()
        footprint_bucket, footprint_intensity = self._bucket_footprint(footprint_acres)
        traffic_bucket, traffic_intensity = self._bucket_traffic(estimated_daily_vehicle_trips)

        submitted_action_inputs, submitted_simulation_actions = self._normalize_actions(
            self._build_actions(
                area=area,
                project_type=project_type,
                buildout_years=buildout_years,
                footprint_intensity=footprint_intensity,
                traffic_intensity=traffic_intensity,
                mitigation_commitment=mitigation_commitment,
            )
        )
        mitigated_action_inputs, mitigated_simulation_actions = self._normalize_actions(
            self._build_actions(
                area=area,
                project_type=project_type,
                buildout_years=buildout_years,
                footprint_intensity=footprint_intensity,
                traffic_intensity=traffic_intensity,
                mitigation_commitment=MitigationCommitment.HIGH,
            )
        )

        submitted_projection = simulation_engine.project_world_result(
            base_world_id=world.world_id,
            actions=submitted_simulation_actions,
            projection_years=DEFAULT_PROJECTION_YEARS,
            mode=SimulationMode.PLANNING,
        )
        mitigated_projection = simulation_engine.project_world_result(
            base_world_id=world.world_id,
            actions=mitigated_simulation_actions,
            projection_years=DEFAULT_PROJECTION_YEARS,
            mode=SimulationMode.PLANNING,
        )
        comparison = simulation_engine.compare_scenarios(
            base_world_id=world.world_id,
            projection_years=DEFAULT_PROJECTION_YEARS,
            mode=SimulationMode.PLANNING,
            scenarios=[
                (SUBMITTED_SCENARIO_NAME, submitted_simulation_actions),
                (MITIGATED_SCENARIO_NAME, mitigated_simulation_actions),
            ],
        )

        recommended_option = (
            "mitigated_plan" if comparison.recommended_scenario == MITIGATED_SCENARIO_NAME else "submitted_plan"
        )
        comparison_summary = comparison.comparison_summary_text
        if comparison.key_tradeoffs:
            comparison_summary = f"{comparison_summary} {comparison.key_tradeoffs[0]}"

        return ProposalAssessmentResponse(
            site_id=site_id,
            area_id=area_id,
            project_type=project_type,
            footprint_acres=round(footprint_acres, 2),
            estimated_daily_vehicle_trips=estimated_daily_vehicle_trips,
            buildout_years=buildout_years,
            mitigation_commitment=mitigation_commitment,
            planner_notes=planner_notes,
            submitted_plan=self._build_scorecard(area, submitted_projection, submitted_action_inputs),
            mitigated_plan=self._build_scorecard(area, mitigated_projection, mitigated_action_inputs),
            recommended_option=recommended_option,
            comparison_summary=comparison_summary,
            simulation_inputs=PlannerSimulationInputsResponse(
                projection_years=DEFAULT_PROJECTION_YEARS,
                baseline_zone_id=area.baseline_zone_id,
                footprint_bucket=footprint_bucket,
                traffic_bucket=traffic_bucket,
                submitted_actions=[
                    PlannerSimulationActionResponse.model_validate(action) for action in submitted_action_inputs
                ],
                mitigated_actions=[
                    PlannerSimulationActionResponse.model_validate(action) for action in mitigated_action_inputs
                ],
            ),
        )


planning_service = PlanningService()
