from __future__ import annotations

import math
from typing import Any

from app.core.constants import RiskLevel
from app.models.api.responses import (
    GeometryLocationSummaryResponse,
    PlanningLocationContextResponse,
    GeometryResolutionResponse,
    PlanScorecardResponse,
    PlanningBuildOptionsResponse,
    PlannerSimulationActionResponse,
    PlannerSimulationInputsResponse,
    PlanningContinentResponse,
    PlanningSiteResponse,
    ProposalAssessmentResponse,
)
from app.models.domain.action import SimulationAction, SimulationMode
from app.models.domain.planning import (
    BuildFieldDefinition,
    BuildSectionDefinition,
    GeometryPoint,
    GeometrySelectionMode,
    InfrastructureCategory,
    MitigationCommitment,
    MapToolDefinition,
    PlanningFieldType,
    PlanVerdict,
    PlannerProjectType,
    PlanningLocationContext,
    PlanningLocationInput,
)
from app.models.domain.simulation import ProjectionSimulationResult
from app.models.domain.zone import ZoneState
from app.services.action_mapper import action_mapper
from app.services.analysis_document_service import analysis_document_service
from app.services.impact_service import impact_service
from app.services.public_baseline_service import GLOBAL_WORLD_ID, public_baseline_service
from app.services.simulation_engine import simulation_engine
from app.services.world_service import world_service


SITE_ID = "global_location_planner"
DEFAULT_PROJECTION_YEARS = 5
SUBMITTED_SCENARIO_NAME = "Submitted Plan"
MITIGATED_SCENARIO_NAME = "Mitigated Plan"

PROJECT_ACTION_MAPPING = {
    PlannerProjectType.INDUSTRIAL_FACILITY: ("industrial_expansion", "expand_roadway"),
    PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION: ("expand_roadway", "industrial_expansion"),
    PlannerProjectType.MIXED_USE_REDEVELOPMENT: ("expand_roadway", "reduce_green_space"),
}

RESTORATION_ACTION_BY_PROJECT = {
    PlannerProjectType.INDUSTRIAL_FACILITY: "add_urban_park",
    PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION: "improve_public_transit",
    PlannerProjectType.MIXED_USE_REDEVELOPMENT: "restoration_corridor",
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

DEFAULT_BUILDOUT_YEARS = {
    InfrastructureCategory.ROAD: 3,
    InfrastructureCategory.BRIDGE: 4,
    InfrastructureCategory.BUILDINGS: 3,
    InfrastructureCategory.AIRPORT: 5,
    InfrastructureCategory.GENERAL_AREA: 2,
    InfrastructureCategory.SOLAR_PANEL: 2,
}

INFRASTRUCTURE_TO_PROJECT_TYPE = {
    InfrastructureCategory.ROAD: PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
    InfrastructureCategory.BRIDGE: PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
    InfrastructureCategory.BUILDINGS: PlannerProjectType.MIXED_USE_REDEVELOPMENT,
    InfrastructureCategory.AIRPORT: PlannerProjectType.INDUSTRIAL_FACILITY,
    InfrastructureCategory.GENERAL_AREA: PlannerProjectType.MIXED_USE_REDEVELOPMENT,
    InfrastructureCategory.SOLAR_PANEL: PlannerProjectType.MIXED_USE_REDEVELOPMENT,
}

BUILD_SECTIONS = [
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.ROAD,
        title="Road",
        summary="Use this section for road segments, corridor widening, or logistics access roads.",
        default_project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.LINE,
            min_points=2,
            max_points=2,
            instructions="Click a road start point, then click the end point. The backend derives road length automatically.",
            auto_derived_fields=["length_km"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="length_km",
                label="Road length",
                field_type=PlanningFieldType.NUMBER,
                unit="km",
                minimum=0.1,
                maximum=200,
                help_text="Total road length to build or expand.",
            ),
            BuildFieldDefinition(
                field_name="lane_count",
                label="Lane count",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=16,
                help_text="Total number of lanes after the project is delivered.",
            ),
            BuildFieldDefinition(
                field_name="paved_area_sq_m",
                label="Paved area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=500,
                maximum=5000000,
                help_text="Estimated paved footprint. Use this if you already know the corridor area.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily vehicle trips once the road is operating.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="How many years the project takes to build.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.BRIDGE,
        title="Bridge",
        summary="Use this section for bridges, flyovers, crossings, or elevated connectors.",
        default_project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.LINE,
            min_points=2,
            max_points=2,
            instructions="Click the bridge start point, then the end point. The backend derives span length automatically.",
            auto_derived_fields=["span_length_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="span_length_m",
                label="Span length",
                field_type=PlanningFieldType.NUMBER,
                unit="m",
                minimum=20,
                maximum=5000,
                help_text="Main bridge span length.",
            ),
            BuildFieldDefinition(
                field_name="deck_width_m",
                label="Deck width",
                field_type=PlanningFieldType.NUMBER,
                unit="m",
                minimum=4,
                maximum=120,
                help_text="Full bridge width including lanes or paths.",
            ),
            BuildFieldDefinition(
                field_name="approach_area_sq_m",
                label="Approach area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=0,
                maximum=5000000,
                help_text="Associated approach and interchange area.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily trips crossing the bridge.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="How many years the bridge work will take.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.BUILDINGS,
        title="Buildings",
        summary="Use this section for residential, commercial, industrial, or civic building clusters.",
        default_project_type=PlannerProjectType.MIXED_USE_REDEVELOPMENT,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=12,
            instructions="Click the site corners in order to draw the building site boundary. The backend derives site area automatically.",
            auto_derived_fields=["site_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="building_count",
                label="Building count",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=500,
                help_text="Number of buildings in the proposal.",
            ),
            BuildFieldDefinition(
                field_name="total_floor_area_sq_m",
                label="Total floor area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Combined floor area across all buildings.",
            ),
            BuildFieldDefinition(
                field_name="site_area_sq_m",
                label="Site area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Total land area covered by the development site.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily vehicle trips generated by the site.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Estimated delivery timeline for the building program.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.AIRPORT,
        title="Airport",
        summary="Use this section for airports, runway upgrades, freight aprons, or terminal expansion.",
        default_project_type=PlannerProjectType.INDUSTRIAL_FACILITY,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.LINE,
            min_points=2,
            max_points=2,
            instructions="Click the runway start point, then the runway end point. The backend derives runway length automatically.",
            auto_derived_fields=["runway_length_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="runway_length_m",
                label="Runway length",
                field_type=PlanningFieldType.NUMBER,
                unit="m",
                minimum=500,
                maximum=5000,
                help_text="Primary runway length.",
            ),
            BuildFieldDefinition(
                field_name="runway_width_m",
                label="Runway width",
                field_type=PlanningFieldType.NUMBER,
                unit="m",
                minimum=20,
                maximum=100,
                help_text="Primary runway width.",
            ),
            BuildFieldDefinition(
                field_name="terminal_area_sq_m",
                label="Terminal area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=0,
                maximum=5000000,
                help_text="Terminal and passenger/service building area.",
            ),
            BuildFieldDefinition(
                field_name="apron_area_sq_m",
                label="Apron area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=0,
                maximum=5000000,
                help_text="Aircraft apron, taxi, and support paved area.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily landside traffic from the airport project.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Estimated airport buildout duration.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.GENERAL_AREA,
        title="General Area",
        summary="Use this section for broad land conversion, district redevelopment, or site preparation studies.",
        default_project_type=PlannerProjectType.MIXED_USE_REDEVELOPMENT,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=16,
            instructions="Click the site corners to draw the general project area. The backend derives total site area automatically.",
            auto_derived_fields=["site_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="site_area_sq_m",
                label="Site area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Total area of the district or parcel under review.",
            ),
            BuildFieldDefinition(
                field_name="impervious_surface_pct",
                label="Impervious surface",
                field_type=PlanningFieldType.NUMBER,
                unit="percent",
                minimum=0,
                maximum=100,
                help_text="Share of the site expected to become paved or hardscaped.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily traffic from the overall area plan.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Expected timeline for the area plan buildout.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.SOLAR_PANEL,
        title="Solar Panel",
        summary="Use this section for ground-mounted solar fields, canopy installations, or solar-plus-storage sites.",
        default_project_type=PlannerProjectType.MIXED_USE_REDEVELOPMENT,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=16,
            instructions="Click the solar field corners to draw the panel boundary. The backend derives panel field area automatically.",
            auto_derived_fields=["panel_field_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="panel_field_area_sq_m",
                label="Panel field area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Total ground area covered by solar panels and support equipment.",
            ),
            BuildFieldDefinition(
                field_name="capacity_mw",
                label="Capacity",
                field_type=PlanningFieldType.NUMBER,
                unit="MW",
                minimum=0.1,
                maximum=5000,
                help_text="Planned generation capacity.",
            ),
            BuildFieldDefinition(
                field_name="battery_storage_mwh",
                label="Battery storage",
                field_type=PlanningFieldType.NUMBER,
                unit="MWh",
                minimum=0,
                maximum=10000,
                help_text="Optional battery storage capacity for the site.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="maintenance_vehicle_trips_per_day",
                label="Maintenance trips per day",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=5000,
                help_text="Expected daily service and maintenance trips.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Expected delivery time for the solar installation.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.HIGHWAY,
        title="Highway",
        summary="Use this section for highways, motorways, freeways, or high-capacity inter-city road corridors.",
        default_project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.LINE,
            min_points=2,
            max_points=2,
            instructions="Click the highway start point, then the end point. The backend derives length automatically.",
            auto_derived_fields=["length_km"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="length_km",
                label="Highway length",
                field_type=PlanningFieldType.NUMBER,
                unit="km",
                minimum=0.5,
                maximum=500,
                help_text="Total highway length to build or expand.",
            ),
            BuildFieldDefinition(
                field_name="lane_count",
                label="Lane count",
                field_type=PlanningFieldType.INTEGER,
                minimum=2,
                maximum=20,
                help_text="Total number of lanes including both directions.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=200000,
                help_text="Expected daily vehicle volume once the highway is operating.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="How many years the highway project takes to deliver.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.BUILDING,
        title="Building",
        summary="Use this section for a single building or small building cluster — residential, commercial, or civic.",
        default_project_type=PlannerProjectType.MIXED_USE_REDEVELOPMENT,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=12,
            instructions="Click the building footprint corners. The backend derives site area automatically.",
            auto_derived_fields=["site_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="building_count",
                label="Building count",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=500,
                help_text="Number of buildings in the proposal.",
            ),
            BuildFieldDefinition(
                field_name="total_floor_area_sq_m",
                label="Total floor area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Combined floor area across all buildings.",
            ),
            BuildFieldDefinition(
                field_name="site_area_sq_m",
                label="Site area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=10000000,
                help_text="Total land area covered by the development site.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily vehicle trips generated by the site.",
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Estimated delivery timeline.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.SOLAR_FARM,
        title="Solar Farm",
        summary="Use this section for large-scale solar farms, utility-scale PV fields, or renewable energy installations.",
        default_project_type=PlannerProjectType.MIXED_USE_REDEVELOPMENT,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=16,
            instructions="Click the solar farm boundary corners. The backend derives panel field area automatically.",
            auto_derived_fields=["panel_field_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="panel_field_area_sq_m",
                label="Panel field area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=100,
                maximum=50000000,
                help_text="Total ground area covered by the solar farm.",
            ),
            BuildFieldDefinition(
                field_name="capacity_mw",
                label="Capacity",
                field_type=PlanningFieldType.NUMBER,
                unit="MW",
                minimum=0.1,
                maximum=10000,
                help_text="Planned generation capacity of the solar farm.",
            ),
            BuildFieldDefinition(
                field_name="battery_storage_mwh",
                label="Battery storage",
                field_type=PlanningFieldType.NUMBER,
                unit="MWh",
                minimum=0,
                maximum=50000,
                help_text="Optional battery storage capacity.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=10,
                help_text="Expected build time for the solar farm.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.DAM,
        title="Dam",
        summary="Use this section for dams, weirs, reservoirs, or hydro-electric infrastructure.",
        default_project_type=PlannerProjectType.INDUSTRIAL_FACILITY,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=12,
            instructions="Click the dam and reservoir boundary. The backend derives reservoir area automatically.",
            auto_derived_fields=["reservoir_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="dam_height_m",
                label="Dam height",
                field_type=PlanningFieldType.NUMBER,
                unit="m",
                minimum=2,
                maximum=300,
                help_text="Height of the dam structure.",
            ),
            BuildFieldDefinition(
                field_name="reservoir_area_sq_m",
                label="Reservoir area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=1000,
                maximum=100000000,
                help_text="Surface area of the reservoir created.",
            ),
            BuildFieldDefinition(
                field_name="capacity_mw",
                label="Hydro capacity",
                field_type=PlanningFieldType.NUMBER,
                unit="MW",
                minimum=0,
                maximum=20000,
                help_text="Hydro-electric generation capacity, if applicable.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Estimated construction timeline.",
                required=False,
            ),
        ],
    ),
    BuildSectionDefinition(
        infrastructure_type=InfrastructureCategory.INDUSTRIAL,
        title="Industrial Facility",
        summary="Use this section for factories, warehouses, logistics hubs, processing plants, or industrial zones.",
        default_project_type=PlannerProjectType.INDUSTRIAL_FACILITY,
        map_tool=MapToolDefinition(
            selection_mode=GeometrySelectionMode.POLYGON,
            min_points=3,
            max_points=12,
            instructions="Click the facility site boundary corners. The backend derives site area automatically.",
            auto_derived_fields=["site_area_sq_m"],
        ),
        fields=[
            BuildFieldDefinition(
                field_name="site_area_sq_m",
                label="Site area",
                field_type=PlanningFieldType.NUMBER,
                unit="sq m",
                minimum=500,
                maximum=50000000,
                help_text="Total land area of the industrial facility.",
            ),
            BuildFieldDefinition(
                field_name="daily_vehicle_trips",
                label="Daily vehicle trips",
                field_type=PlanningFieldType.INTEGER,
                minimum=0,
                maximum=50000,
                help_text="Expected daily truck and vehicle trips to/from the facility.",
            ),
            BuildFieldDefinition(
                field_name="building_count",
                label="Building count",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=100,
                help_text="Number of industrial structures on site.",
                required=False,
            ),
            BuildFieldDefinition(
                field_name="construction_years",
                label="Construction years",
                field_type=PlanningFieldType.INTEGER,
                minimum=1,
                maximum=25,
                help_text="Estimated construction and fit-out timeline.",
                required=False,
            ),
        ],
    ),
]


class PlanningService:
    def _location_context_response(self, context: PlanningLocationContext) -> PlanningLocationContextResponse:
        return PlanningLocationContextResponse.model_validate(context.model_dump())

    def _find_zone(self, zone_id: str) -> ZoneState:
        world = world_service.get_world()
        for zone in world.zones:
            if zone.zone_id == zone_id:
                return zone
        raise ValueError(f"Zone '{zone_id}' was not found.")

    def get_build_options(self) -> PlanningBuildOptionsResponse:
        return PlanningBuildOptionsResponse(site_id=SITE_ID, sections=BUILD_SECTIONS)

    def get_build_section_definition(self, infrastructure_type: InfrastructureCategory) -> BuildSectionDefinition:
        return self._get_build_section(infrastructure_type)

    def _get_build_section(self, infrastructure_type: InfrastructureCategory) -> BuildSectionDefinition:
        for section in BUILD_SECTIONS:
            if section.infrastructure_type == infrastructure_type:
                return section
        raise ValueError(f"Unsupported infrastructure_type '{infrastructure_type.value}'.")

    def _validate_geometry_points(
        self,
        infrastructure_type: InfrastructureCategory,
        geometry_points: list[GeometryPoint],
    ) -> tuple[BuildSectionDefinition, list[GeometryPoint]]:
        section = self._get_build_section(infrastructure_type)
        map_tool = section.map_tool
        if map_tool is None:
            raise ValueError(f"Infrastructure type '{infrastructure_type.value}' does not support map geometry.")
        if len(geometry_points) < map_tool.min_points or len(geometry_points) > map_tool.max_points:
            raise ValueError(
                f"Infrastructure type '{infrastructure_type.value}' expects between "
                f"{map_tool.min_points} and {map_tool.max_points} geometry points."
            )
        return section, geometry_points

    def _haversine_distance_m(self, first: GeometryPoint, second: GeometryPoint) -> float:
        earth_radius_m = 6371000.0
        lat1 = math.radians(first.latitude)
        lat2 = math.radians(second.latitude)
        delta_lat = lat2 - lat1
        delta_lng = math.radians(second.longitude - first.longitude)

        haversine = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
        )
        return 2 * earth_radius_m * math.asin(math.sqrt(haversine))

    def _to_local_xy(self, points: list[GeometryPoint]) -> list[tuple[float, float]]:
        reference_latitude = math.radians(sum(point.latitude for point in points) / len(points))
        meters_per_degree_lat = 111320.0
        meters_per_degree_lng = 111320.0 * math.cos(reference_latitude)
        origin = points[0]

        return [
            (
                (point.longitude - origin.longitude) * meters_per_degree_lng,
                (point.latitude - origin.latitude) * meters_per_degree_lat,
            )
            for point in points
        ]

    def _polygon_area_sq_m(self, points: list[GeometryPoint]) -> float:
        local_points = self._to_local_xy(points)
        area = 0.0
        for index, (x1, y1) in enumerate(local_points):
            x2, y2 = local_points[(index + 1) % len(local_points)]
            area += (x1 * y2) - (x2 * y1)
        return abs(area) / 2.0

    def _line_center_point(self, points: list[GeometryPoint]) -> GeometryPoint:
        start, end = points[0], points[-1]
        return GeometryPoint(
            latitude=round((start.latitude + end.latitude) / 2.0, 7),
            longitude=round((start.longitude + end.longitude) / 2.0, 7),
        )

    def _polygon_center_point(self, points: list[GeometryPoint]) -> GeometryPoint:
        return GeometryPoint(
            latitude=round(sum(point.latitude for point in points) / len(points), 7),
            longitude=round(sum(point.longitude for point in points) / len(points), 7),
        )

    def _build_geometry_summary(
        self,
        infrastructure_type: InfrastructureCategory,
        geometry_points: list[GeometryPoint],
    ) -> GeometryLocationSummaryResponse:
        section, normalized_points = self._validate_geometry_points(infrastructure_type, geometry_points)
        map_tool = section.map_tool
        assert map_tool is not None

        if map_tool.selection_mode == GeometrySelectionMode.LINE:
            length_m = round(self._haversine_distance_m(normalized_points[0], normalized_points[-1]), 2)
            return GeometryLocationSummaryResponse(
                selection_mode=map_tool.selection_mode.value,
                point_count=len(normalized_points),
                start_point=normalized_points[0],
                end_point=normalized_points[-1],
                center_point=self._line_center_point(normalized_points),
                length_m=length_m,
                area_sq_m=None,
            )

        area_sq_m = round(self._polygon_area_sq_m(normalized_points), 2)
        return GeometryLocationSummaryResponse(
            selection_mode=map_tool.selection_mode.value,
            point_count=len(normalized_points),
            start_point=normalized_points[0],
            end_point=normalized_points[-1],
            center_point=self._polygon_center_point(normalized_points),
            length_m=None,
            area_sq_m=area_sq_m,
        )

    def _merge_geometry_into_details(
        self,
        infrastructure_type: InfrastructureCategory,
        infrastructure_details: dict[str, Any],
        geometry_summary: GeometryLocationSummaryResponse | None,
    ) -> dict[str, Any]:
        if geometry_summary is None:
            return dict(infrastructure_details)

        merged_details = dict(infrastructure_details)
        if infrastructure_type == InfrastructureCategory.ROAD and geometry_summary.length_m is not None:
            merged_details.setdefault("length_km", round(geometry_summary.length_m / 1000.0, 3))
        elif infrastructure_type == InfrastructureCategory.BRIDGE and geometry_summary.length_m is not None:
            merged_details.setdefault("span_length_m", geometry_summary.length_m)
        elif infrastructure_type == InfrastructureCategory.AIRPORT and geometry_summary.length_m is not None:
            merged_details.setdefault("runway_length_m", geometry_summary.length_m)
        elif infrastructure_type == InfrastructureCategory.BUILDINGS and geometry_summary.area_sq_m is not None:
            merged_details.setdefault("site_area_sq_m", geometry_summary.area_sq_m)
        elif infrastructure_type == InfrastructureCategory.GENERAL_AREA and geometry_summary.area_sq_m is not None:
            merged_details.setdefault("site_area_sq_m", geometry_summary.area_sq_m)
        elif infrastructure_type == InfrastructureCategory.SOLAR_PANEL and geometry_summary.area_sq_m is not None:
            merged_details.setdefault("panel_field_area_sq_m", geometry_summary.area_sq_m)

        return merged_details

    def resolve_geometry(
        self,
        location: PlanningLocationInput,
        infrastructure_type: InfrastructureCategory,
        geometry_points: list[GeometryPoint],
        infrastructure_details: dict[str, Any] | None = None,
    ) -> GeometryResolutionResponse:
        location_context = public_baseline_service.build_location_context(location)
        geometry_summary = self._build_geometry_summary(infrastructure_type, geometry_points)
        merged_details = self._merge_geometry_into_details(
            infrastructure_type=infrastructure_type,
            infrastructure_details=infrastructure_details or {},
            geometry_summary=geometry_summary,
        )
        normalized_details = self._validate_infrastructure_details(infrastructure_type, merged_details)

        return GeometryResolutionResponse(
            location_context=self._location_context_response(location_context),
            infrastructure_type=infrastructure_type,
            resolved_project_type=INFRASTRUCTURE_TO_PROJECT_TYPE[infrastructure_type],
            geometry_summary=geometry_summary,
            resolved_infrastructure_details=normalized_details,
        )

    def build_geometry_summary(
        self,
        infrastructure_type: InfrastructureCategory,
        geometry_points: list[GeometryPoint],
    ) -> GeometryLocationSummaryResponse:
        return self._build_geometry_summary(infrastructure_type, geometry_points)

    def merge_geometry_details(
        self,
        infrastructure_type: InfrastructureCategory,
        infrastructure_details: dict[str, Any],
        geometry_summary: GeometryLocationSummaryResponse | None,
    ) -> dict[str, Any]:
        return self._merge_geometry_into_details(
            infrastructure_type=infrastructure_type,
            infrastructure_details=infrastructure_details,
            geometry_summary=geometry_summary,
        )

    def _coerce_numeric_value(self, value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"Field '{field_name}' must be a number.")
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"Field '{field_name}' must be a number.")

    def _validate_infrastructure_details(
        self,
        infrastructure_type: InfrastructureCategory,
        infrastructure_details: dict[str, Any],
    ) -> dict[str, str | int | float | bool]:
        section = self._get_build_section(infrastructure_type)
        normalized: dict[str, str | int | float | bool] = {}

        for field in section.fields:
            value = infrastructure_details.get(field.field_name)
            if value is None:
                if field.required:
                    raise ValueError(
                        f"Field '{field.field_name}' is required for infrastructure_type "
                        f"'{infrastructure_type.value}'."
                    )
                continue

            if field.field_type in {PlanningFieldType.NUMBER, PlanningFieldType.INTEGER}:
                numeric_value = self._coerce_numeric_value(value, field.field_name)
                if field.minimum is not None and numeric_value < field.minimum:
                    raise ValueError(f"Field '{field.field_name}' must be >= {field.minimum}.")
                if field.maximum is not None and numeric_value > field.maximum:
                    raise ValueError(f"Field '{field.field_name}' must be <= {field.maximum}.")
                if field.field_type == PlanningFieldType.INTEGER:
                    normalized[field.field_name] = int(round(numeric_value))
                else:
                    normalized[field.field_name] = round(numeric_value, 2)
            else:
                normalized[field.field_name] = str(value).strip()

        return normalized

    def _sq_m_to_acres(self, area_sq_m: float) -> float:
        return round(area_sq_m / 4046.8564224, 2)

    def _resolve_infrastructure_inputs(
        self,
        infrastructure_type: InfrastructureCategory,
        infrastructure_details: dict[str, Any],
    ) -> tuple[PlannerProjectType, dict[str, str | int | float | bool], float, int, int]:
        details = self._validate_infrastructure_details(infrastructure_type, infrastructure_details)
        project_type = INFRASTRUCTURE_TO_PROJECT_TYPE[infrastructure_type]

        if infrastructure_type == InfrastructureCategory.ROAD:
            paved_area_sq_m = float(
                details.get("paved_area_sq_m", float(details["length_km"]) * 1000 * float(details["lane_count"]) * 3.5)
            )
            footprint_acres = self._sq_m_to_acres(paved_area_sq_m)
            traffic = int(details["daily_vehicle_trips"])
        elif infrastructure_type == InfrastructureCategory.BRIDGE:
            bridge_area_sq_m = (float(details["span_length_m"]) * float(details["deck_width_m"])) + float(
                details.get("approach_area_sq_m", 0)
            )
            footprint_acres = self._sq_m_to_acres(bridge_area_sq_m)
            traffic = int(details["daily_vehicle_trips"])
        elif infrastructure_type == InfrastructureCategory.BUILDINGS:
            footprint_acres = self._sq_m_to_acres(float(details["site_area_sq_m"]))
            traffic = int(details["daily_vehicle_trips"])
        elif infrastructure_type == InfrastructureCategory.AIRPORT:
            runway_area_sq_m = float(details["runway_length_m"]) * float(details["runway_width_m"])
            airport_area_sq_m = runway_area_sq_m + float(details["terminal_area_sq_m"]) + float(details["apron_area_sq_m"])
            footprint_acres = self._sq_m_to_acres(airport_area_sq_m)
            traffic = int(details["daily_vehicle_trips"])
        elif infrastructure_type == InfrastructureCategory.GENERAL_AREA:
            developed_area_sq_m = float(details["site_area_sq_m"]) * (float(details["impervious_surface_pct"]) / 100.0)
            footprint_acres = self._sq_m_to_acres(developed_area_sq_m or float(details["site_area_sq_m"]))
            traffic = int(details["daily_vehicle_trips"])
        else:
            footprint_acres = self._sq_m_to_acres(float(details["panel_field_area_sq_m"]))
            traffic = int(details["maintenance_vehicle_trips_per_day"])

        buildout_years = int(details.get("construction_years", DEFAULT_BUILDOUT_YEARS[infrastructure_type]))
        return project_type, details, footprint_acres, traffic, buildout_years

    def resolve_infrastructure_inputs(
        self,
        infrastructure_type: InfrastructureCategory,
        infrastructure_details: dict[str, Any],
    ) -> tuple[PlannerProjectType, dict[str, str | int | float | bool], float, int, int]:
        return self._resolve_infrastructure_inputs(infrastructure_type, infrastructure_details)

    def get_site(self) -> PlanningSiteResponse:
        continents = []
        for continent in public_baseline_service.list_continents():
            zone = self._find_zone(continent.zone_id)
            continents.append(
                PlanningContinentResponse(
                    continent_id=continent.continent_id,
                    name=continent.name,
                    baseline_zone_id=continent.zone_id,
                    current_risk_level=zone.risk_level.value,
                    planning_notes=continent.summary,
                    allowed_project_types=list(PlannerProjectType),
                )
            )

        return PlanningSiteResponse(
            site_id=SITE_ID,
            name="Global Location Planner",
            state="Global",
            summary=(
                "Location-first planner for real-world coordinates. Choose anywhere on Earth, resolve the "
                "continent context, bring in live public baseline data, and simulate infrastructure impact "
                "from that current baseline instead of a preset demo parcel."
            ),
            continents=continents,
            build_sections=BUILD_SECTIONS,
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
        baseline_zone_id: str,
        project_type: PlannerProjectType,
        buildout_years: int,
        footprint_intensity: float,
        traffic_intensity: float,
        mitigation_commitment: MitigationCommitment,
    ) -> list[dict[str, object]]:
        primary_action, secondary_action = PROJECT_ACTION_MAPPING[project_type]
        actions: list[dict[str, object]] = [
            {
                "zone_id": baseline_zone_id,
                "requested_action_type": primary_action,
                "intensity": footprint_intensity,
                "duration_years": buildout_years,
            },
            {
                "zone_id": baseline_zone_id,
                "requested_action_type": secondary_action,
                "intensity": traffic_intensity,
                "duration_years": buildout_years,
            },
        ]

        restoration_action = RESTORATION_ACTION_BY_PROJECT[project_type]
        mitigation_duration = min(buildout_years, DEFAULT_PROJECTION_YEARS)

        if mitigation_commitment in {MitigationCommitment.MEDIUM, MitigationCommitment.HIGH}:
            actions.append(
                {
                    "zone_id": baseline_zone_id,
                    "requested_action_type": restoration_action,
                    "intensity": 0.6 if mitigation_commitment == MitigationCommitment.MEDIUM else 0.85,
                    "duration_years": mitigation_duration,
                }
            )

        if mitigation_commitment == MitigationCommitment.HIGH:
            actions.append(
                {
                    "zone_id": baseline_zone_id,
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
        project_type: PlannerProjectType,
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

        restoration_action = RESTORATION_ACTION_BY_PROJECT[project_type]
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
        project_type: PlannerProjectType,
        projection: ProjectionSimulationResult,
        action_inputs: list[dict[str, object]],
    ) -> PlanScorecardResponse:
        return PlanScorecardResponse(
            plan_score=round(projection.sustainability_score, 2),
            verdict=self._resolve_verdict(projection),
            overall_outlook=projection.overall_outlook,
            highest_risk_zone=impact_service.build_compact_zone_summary(projection.highest_risk_zone),
            top_risks=projection.highest_risk_zone_top_drivers or ["No concentrated high-risk drivers were detected."],
            required_mitigations=self._build_required_mitigations(project_type, projection, action_inputs),
            summary_text=projection.summary_text,
        )

    def assess_proposal(
        self,
        location: PlanningLocationInput,
        project_type: PlannerProjectType | None,
        infrastructure_type: InfrastructureCategory | None,
        geometry_points: list[GeometryPoint] | None,
        infrastructure_details: dict[str, Any] | None,
        footprint_acres: float | None,
        estimated_daily_vehicle_trips: int | None,
        buildout_years: int | None,
        mitigation_commitment: MitigationCommitment,
        planner_notes: str | None = None,
    ) -> ProposalAssessmentResponse:
        location_context, location_zone = public_baseline_service.build_location_zone(location)

        normalized_infrastructure_details: dict[str, str | int | float | bool] = {}
        geometry_summary: GeometryLocationSummaryResponse | None = None
        if infrastructure_type is not None:
            if geometry_points:
                geometry_resolution = self.resolve_geometry(
                    location=location,
                    infrastructure_type=infrastructure_type,
                    geometry_points=geometry_points,
                    infrastructure_details=infrastructure_details or {},
                )
                geometry_summary = geometry_resolution.geometry_summary
                merged_infrastructure_details: dict[str, Any] = dict(geometry_resolution.resolved_infrastructure_details)
            else:
                merged_infrastructure_details = dict(infrastructure_details or {})

            (
                resolved_project_type,
                normalized_infrastructure_details,
                resolved_footprint_acres,
                resolved_estimated_daily_vehicle_trips,
                resolved_buildout_years,
            ) = self._resolve_infrastructure_inputs(infrastructure_type, merged_infrastructure_details)
        else:
            if project_type is None or footprint_acres is None or estimated_daily_vehicle_trips is None or buildout_years is None:
                raise ValueError(
                    "Legacy proposal mode requires project_type, footprint_acres, estimated_daily_vehicle_trips, "
                    "and buildout_years."
                )
            resolved_project_type = project_type
            resolved_footprint_acres = footprint_acres
            resolved_estimated_daily_vehicle_trips = estimated_daily_vehicle_trips
            resolved_buildout_years = buildout_years

        world = world_service.get_world()
        baseline_world = world.model_copy(deep=True)
        for index, zone in enumerate(baseline_world.zones):
            if zone.zone_id == location_context.baseline_zone_id:
                baseline_world.zones[index] = location_zone
                break

        footprint_bucket, footprint_intensity = self._bucket_footprint(resolved_footprint_acres)
        traffic_bucket, traffic_intensity = self._bucket_traffic(resolved_estimated_daily_vehicle_trips)

        submitted_action_inputs, submitted_simulation_actions = self._normalize_actions(
            self._build_actions(
                baseline_zone_id=location_context.baseline_zone_id,
                project_type=resolved_project_type,
                buildout_years=resolved_buildout_years,
                footprint_intensity=footprint_intensity,
                traffic_intensity=traffic_intensity,
                mitigation_commitment=mitigation_commitment,
            )
        )
        mitigated_action_inputs, mitigated_simulation_actions = self._normalize_actions(
            self._build_actions(
                baseline_zone_id=location_context.baseline_zone_id,
                project_type=resolved_project_type,
                buildout_years=resolved_buildout_years,
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
            base_world_override=baseline_world,
        )
        mitigated_projection = simulation_engine.project_world_result(
            base_world_id=world.world_id,
            actions=mitigated_simulation_actions,
            projection_years=DEFAULT_PROJECTION_YEARS,
            mode=SimulationMode.PLANNING,
            base_world_override=baseline_world,
        )
        comparison = simulation_engine.compare_scenarios(
            base_world_id=world.world_id,
            projection_years=DEFAULT_PROJECTION_YEARS,
            mode=SimulationMode.PLANNING,
            scenarios=[
                (SUBMITTED_SCENARIO_NAME, submitted_simulation_actions),
                (MITIGATED_SCENARIO_NAME, mitigated_simulation_actions),
            ],
            base_world_override=baseline_world,
        )

        recommended_option = (
            "mitigated_plan" if comparison.recommended_scenario == MITIGATED_SCENARIO_NAME else "submitted_plan"
        )
        comparison_summary = comparison.comparison_summary_text
        if comparison.key_tradeoffs:
            comparison_summary = f"{comparison_summary} {comparison.key_tradeoffs[0]}"

        submitted_scorecard = self._build_scorecard(resolved_project_type, submitted_projection, submitted_action_inputs)
        mitigated_scorecard = self._build_scorecard(resolved_project_type, mitigated_projection, mitigated_action_inputs)
        analysis_document = analysis_document_service.build_document(
            location_label=location_context.label,
            planner_notes=planner_notes,
            infrastructure_type=infrastructure_type,
            project_type=resolved_project_type,
            baseline_zone=location_zone,
            baseline_zone_id=location_context.baseline_zone_id,
            submitted_projection=submitted_projection,
            mitigated_projection=mitigated_projection,
            submitted_actions=submitted_action_inputs,
            mitigated_actions=mitigated_action_inputs,
            submitted_top_risks=submitted_scorecard.top_risks,
            mitigated_top_risks=mitigated_scorecard.top_risks,
            recommended_option=recommended_option,
        )

        return ProposalAssessmentResponse(
            location_context=self._location_context_response(location_context),
            continent_id=location_context.continent_id,
            project_type=resolved_project_type,
            infrastructure_type=infrastructure_type,
            geometry_summary=geometry_summary,
            infrastructure_details=normalized_infrastructure_details,
            footprint_acres=round(resolved_footprint_acres, 2),
            estimated_daily_vehicle_trips=resolved_estimated_daily_vehicle_trips,
            buildout_years=resolved_buildout_years,
            mitigation_commitment=mitigation_commitment,
            planner_notes=planner_notes,
            submitted_plan=submitted_scorecard,
            mitigated_plan=mitigated_scorecard,
            recommended_option=recommended_option,
            comparison_summary=comparison_summary,
            analysis_document=analysis_document,
            simulation_inputs=PlannerSimulationInputsResponse(
                projection_years=DEFAULT_PROJECTION_YEARS,
                baseline_zone_id=location_context.baseline_zone_id,
                continent_id=location_context.continent_id,
                footprint_bucket=footprint_bucket,
                traffic_bucket=traffic_bucket,
                resolved_project_type=resolved_project_type,
                location_context=self._location_context_response(location_context),
                infrastructure_type=infrastructure_type,
                geometry_summary=geometry_summary,
                infrastructure_details=normalized_infrastructure_details,
                submitted_actions=[
                    PlannerSimulationActionResponse.model_validate(action) for action in submitted_action_inputs
                ],
                mitigated_actions=[
                    PlannerSimulationActionResponse.model_validate(action) for action in mitigated_action_inputs
                ],
            ),
        )


planning_service = PlanningService()
