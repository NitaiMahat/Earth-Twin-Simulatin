from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.constants import RiskLevel
from app.main import app
from app.models.domain.planning import MitigationCommitment, PlanVerdict, PlannerProjectType, PlanningLocationInput
from app.services.gemini_service import gemini_service
from app.services.planning_service import planning_service
from app.services.public_baseline_service import public_baseline_service


client = TestClient(app)

CHICAGO_LOCATION = {
    "latitude": 41.8781,
    "longitude": -87.6298,
    "label": "Chicago Test Location",
    "country_code": "USA",
}

SYDNEY_SOLAR_LOCATION = {
    "latitude": -33.8688,
    "longitude": 151.2093,
    "label": "Sydney Test Location",
    "country_code": "AUS",
}


def test_get_planning_site_returns_global_continent_metadata() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/planning/site")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == "global_location_planner"
    assert payload["state"] == "Global"
    assert len(payload["continents"]) == 7
    assert payload["continents"][0]["baseline_zone_id"].startswith("continent_")
    assert "industrial_facility" in payload["continents"][0]["allowed_project_types"]
    assert len(payload["build_sections"]) == 6


def test_get_build_options_returns_section_specific_fields() -> None:
    response = client.get("/api/v1/planning/build-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == "global_location_planner"
    assert len(payload["sections"]) == 6

    airport_section = next(
        section for section in payload["sections"] if section["infrastructure_type"] == "airport"
    )
    field_names = [field["field_name"] for field in airport_section["fields"]]

    assert "runway_length_m" in field_names
    assert "runway_width_m" in field_names
    assert "terminal_area_sq_m" in field_names
    assert "apron_area_sq_m" in field_names
    assert airport_section["map_tool"]["selection_mode"] == "line"
    assert airport_section["map_tool"]["min_points"] == 2


def test_resolve_geometry_returns_line_metrics_for_road() -> None:
    response = client.post(
        "/api/v1/planning/geometry/resolve",
        json={
            "location": CHICAGO_LOCATION,
            "infrastructure_type": "road",
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401}
            ],
            "infrastructure_details": {
                "lane_count": 4,
                "daily_vehicle_trips": 1800,
                "construction_years": 3
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved_project_type"] == "roadway_logistics_expansion"
    assert payload["location_context"]["continent_id"] == "north_america"
    assert payload["geometry_summary"]["selection_mode"] == "line"
    assert payload["geometry_summary"]["length_m"] > 0
    assert payload["resolved_infrastructure_details"]["length_km"] > 0


def test_resolve_geometry_enriches_location_with_reverse_geocoded_country(monkeypatch) -> None:
    public_baseline_service._cache.clear()

    original_request_json = public_baseline_service._request_json

    def fake_request(url: str, params: dict[str, object]) -> object:
        if "nominatim" in url:
            return {
                "address": {
                    "country_code": "us",
                    "country": "United States",
                    "state": "Illinois",
                    "city": "Chicago",
                }
            }
        return original_request_json(url, params)

    monkeypatch.setattr(public_baseline_service, "_request_json", fake_request)

    response = client.post(
        "/api/v1/planning/geometry/resolve",
        json={
            "location": {
                "latitude": 41.8781,
                "longitude": -87.6298
            },
            "infrastructure_type": "road",
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401}
            ],
            "infrastructure_details": {
                "lane_count": 4,
                "daily_vehicle_trips": 1800,
                "construction_years": 3
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["location_context"]["country_code"] == "USA"
    assert payload["location_context"]["country_name"] == "United States"
    assert payload["location_context"]["state_name"] == "Illinois"


def test_resolve_geometry_returns_polygon_metrics_for_solar_panel() -> None:
    response = client.post(
        "/api/v1/planning/geometry/resolve",
        json={
            "location": SYDNEY_SOLAR_LOCATION,
            "infrastructure_type": "solar_panel",
            "geometry_points": [
                {"latitude": -33.8600, "longitude": 151.2000},
                {"latitude": -33.8600, "longitude": 151.2030},
                {"latitude": -33.8630, "longitude": 151.2030},
                {"latitude": -33.8630, "longitude": 151.2000}
            ],
            "infrastructure_details": {
                "capacity_mw": 5.5,
                "maintenance_vehicle_trips_per_day": 12
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["location_context"]["continent_id"] == "oceania"
    assert payload["geometry_summary"]["selection_mode"] == "polygon"
    assert payload["geometry_summary"]["area_sq_m"] > 0
    assert payload["resolved_infrastructure_details"]["panel_field_area_sq_m"] > 0


def test_assess_proposal_returns_scorecards_and_simulation_inputs() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": CHICAGO_LOCATION,
            "project_type": "industrial_facility",
            "footprint_acres": 45,
            "estimated_daily_vehicle_trips": 2600,
            "buildout_years": 4,
            "mitigation_commitment": "low",
            "planner_notes": "Freight-oriented advanced manufacturing campus.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["location_context"]["continent_id"] == "north_america"
    assert payload["submitted_plan"]["verdict"] in {"recommended", "conditional", "not_recommended"}
    assert payload["mitigated_plan"]["verdict"] in {"recommended", "conditional", "not_recommended"}
    assert payload["recommended_option"] in {"submitted_plan", "mitigated_plan"}
    assert payload["simulation_inputs"]["projection_years"] == 5
    assert payload["simulation_inputs"]["footprint_bucket"] == "large"
    assert payload["simulation_inputs"]["traffic_bucket"] == "high"
    assert len(payload["simulation_inputs"]["submitted_actions"]) == 2
    assert len(payload["simulation_inputs"]["mitigated_actions"]) >= 3
    assert payload["simulation_inputs"]["submitted_actions"][0]["normalized_action_type"] == "pollution_spike"
    assert payload["analysis_document"]["summary"]
    assert payload["analysis_document"]["metric_cards"]
    assert payload["analysis_document"]["sections"]["executive_summary"]


def test_assess_proposal_accepts_infrastructure_specific_airport_details() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": CHICAGO_LOCATION,
            "infrastructure_type": "airport",
            "infrastructure_details": {
                "runway_length_m": 2400,
                "runway_width_m": 45,
                "terminal_area_sq_m": 18000,
                "apron_area_sq_m": 42000,
                "daily_vehicle_trips": 3200,
                "construction_years": 5
            },
            "mitigation_commitment": "medium",
            "planner_notes": "Regional cargo airport expansion."
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["infrastructure_type"] == "airport"
    assert payload["project_type"] == "industrial_facility"
    assert payload["buildout_years"] == 5
    assert payload["estimated_daily_vehicle_trips"] == 3200
    assert payload["footprint_acres"] > 0
    assert payload["simulation_inputs"]["resolved_project_type"] == "industrial_facility"
    assert payload["simulation_inputs"]["infrastructure_details"]["runway_length_m"] == 2400


def test_assess_proposal_accepts_geometry_points_for_airport_runway() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": CHICAGO_LOCATION,
            "infrastructure_type": "airport",
            "geometry_points": [
                {"latitude": 41.6400, "longitude": -87.5700},
                {"latitude": 41.6540, "longitude": -87.5450}
            ],
            "infrastructure_details": {
                "runway_width_m": 45,
                "terminal_area_sq_m": 18000,
                "apron_area_sq_m": 42000,
                "daily_vehicle_trips": 3200,
                "construction_years": 5
            },
            "mitigation_commitment": "medium"
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["geometry_summary"]["length_m"] > 0
    assert payload["infrastructure_details"]["runway_length_m"] > 0
    assert payload["simulation_inputs"]["geometry_summary"]["selection_mode"] == "line"


def test_assess_proposal_validates_numeric_ranges() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": CHICAGO_LOCATION,
            "project_type": "roadway_logistics_expansion",
            "footprint_acres": 0,
            "estimated_daily_vehicle_trips": 900,
            "buildout_years": 3,
            "mitigation_commitment": "medium",
        },
    )

    assert response.status_code == 422


def test_assess_proposal_rejects_missing_required_infrastructure_fields() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": CHICAGO_LOCATION,
            "infrastructure_type": "airport",
            "infrastructure_details": {
                "runway_length_m": 2400,
                "daily_vehicle_trips": 3200
            },
            "mitigation_commitment": "medium"
        },
    )

    assert response.status_code == 422


def test_assess_proposal_rejects_invalid_geometry_point_count() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "location": SYDNEY_SOLAR_LOCATION,
            "infrastructure_type": "solar_panel",
            "geometry_points": [
                {"latitude": -33.8600, "longitude": 151.2000},
                {"latitude": -33.8600, "longitude": 151.2030}
            ],
            "infrastructure_details": {
                "capacity_mw": 5.5,
                "maintenance_vehicle_trips_per_day": 12
            },
            "mitigation_commitment": "medium"
        },
    )

    assert response.status_code == 422


def test_planning_service_maps_project_type_and_mitigation_commitment_deterministically() -> None:
    client.post("/api/v1/world/reset")
    location = PlanningLocationInput.model_validate(CHICAGO_LOCATION)
    low_commitment = planning_service.assess_proposal(
        location=location,
        project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        infrastructure_type=None,
        geometry_points=[],
        infrastructure_details={},
        footprint_acres=12,
        estimated_daily_vehicle_trips=1500,
        buildout_years=3,
        mitigation_commitment=MitigationCommitment.LOW,
    )
    high_commitment = planning_service.assess_proposal(
        location=location,
        project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        infrastructure_type=None,
        geometry_points=[],
        infrastructure_details={},
        footprint_acres=12,
        estimated_daily_vehicle_trips=1500,
        buildout_years=3,
        mitigation_commitment=MitigationCommitment.HIGH,
    )

    low_actions = [action.requested_action_type for action in low_commitment.simulation_inputs.submitted_actions]
    high_actions = [action.requested_action_type for action in high_commitment.simulation_inputs.submitted_actions]

    assert low_actions == ["expand_roadway", "industrial_expansion"]
    assert "improve_public_transit" in high_actions
    assert high_commitment.simulation_inputs.submitted_actions[0].normalized_action_type == "traffic_increase"


def test_verdict_mapping_covers_positive_mixed_and_negative() -> None:
    positive_projection = SimpleNamespace(
        overall_outlook="positive",
        projected_world=SimpleNamespace(zones=[SimpleNamespace(risk_level=RiskLevel.LOW)]),
    )
    mixed_projection = SimpleNamespace(
        overall_outlook="mixed",
        projected_world=SimpleNamespace(zones=[SimpleNamespace(risk_level=RiskLevel.HIGH)]),
    )
    negative_projection = SimpleNamespace(
        overall_outlook="positive",
        projected_world=SimpleNamespace(zones=[SimpleNamespace(risk_level=RiskLevel.CRITICAL)]),
    )

    assert planning_service._resolve_verdict(positive_projection) == PlanVerdict.RECOMMENDED
    assert planning_service._resolve_verdict(mixed_projection) == PlanVerdict.CONDITIONAL
    assert planning_service._resolve_verdict(negative_projection) == PlanVerdict.NOT_RECOMMENDED


def test_text_draft_for_airport_prompt_derives_runway_length_and_fields(monkeypatch) -> None:
    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        return {
            "infrastructure_type": "airport",
            "project_type": "industrial_facility",
            "planner_summary": "Cargo airport expansion with a widened runway and support apron.",
            "infrastructure_details": {
                "runway_width_m": 45,
                "terminal_area_sq_m": 18000,
                "apron_area_sq_m": 42000,
                "daily_vehicle_trips": 3200,
                "construction_years": 5,
            },
            "missing_fields": [],
            "assumptions": [],
            "confidence": 0.92,
            "simulation_ready": True,
        }

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6400, "longitude": -87.5700},
                {"latitude": 41.6540, "longitude": -87.5450},
            ],
            "user_prompt": "I want to build a cargo airport in this area with a wide runway, terminal, and apron.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["infrastructure_type"] == "airport"
    assert payload["project_type"] == "industrial_facility"
    assert payload["geometry_summary"]["length_m"] > 0
    assert payload["infrastructure_details"]["runway_length_m"] > 0
    assert payload["buildout_years"] == 5
    assert payload["simulation_ready"] is True


def test_text_draft_for_road_prompt_derives_length_and_fields(monkeypatch) -> None:
    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        return {
            "infrastructure_type": "road",
            "project_type": "roadway_logistics_expansion",
            "planner_summary": "Four-lane logistics road segment with moderate freight traffic.",
            "infrastructure_details": {
                "lane_count": 4,
                "daily_vehicle_trips": 1800,
                "construction_years": 3,
            },
            "missing_fields": [],
            "assumptions": [],
            "confidence": 0.88,
            "simulation_ready": True,
        }

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "Build a four lane road corridor here for freight traffic.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["infrastructure_type"] == "road"
    assert payload["project_type"] == "roadway_logistics_expansion"
    assert payload["infrastructure_details"]["length_km"] > 0
    assert payload["estimated_daily_vehicle_trips"] == 1800
    assert payload["simulation_ready"] is True


def test_text_draft_rejects_unsupported_prompt() -> None:
    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "I want to build a solar farm in this area.",
        },
    )

    assert response.status_code == 422
    assert "supports only airport and road" in response.json()["detail"]


def test_text_draft_returns_low_confidence_for_ambiguous_prompt(monkeypatch) -> None:
    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        return {
            "infrastructure_type": None,
            "project_type": None,
            "planner_summary": "Linear transport project in the selected area.",
            "infrastructure_details": {},
            "missing_fields": ["infrastructure_type"],
            "assumptions": ["Could refer to a road or an airport runway."],
            "confidence": 0.41,
            "simulation_ready": False,
        }

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "I want to build transport infrastructure here.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["infrastructure_type"] is None
    assert payload["simulation_ready"] is False
    assert payload["confidence"] == 0.41
    assert "infrastructure_type" in payload["missing_fields"]


def test_text_run_uses_overrides_and_returns_assessment(monkeypatch) -> None:
    client.post("/api/v1/world/reset")

    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        return {
            "infrastructure_type": "road",
            "project_type": "roadway_logistics_expansion",
            "planner_summary": "Road corridor expansion.",
            "infrastructure_details": {
                "lane_count": 4,
                "daily_vehicle_trips": 1800,
            },
            "missing_fields": [],
            "assumptions": [],
            "confidence": 0.9,
            "simulation_ready": True,
        }

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/run",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "Build a road here for freight movement.",
            "mitigation_commitment": "medium",
            "confirmed_overrides": {
                "infrastructure_details": {
                    "lane_count": 6,
                    "daily_vehicle_trips": 2200,
                    "construction_years": 4,
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment"]["project_type"] == "roadway_logistics_expansion"
    assert payload["assessment"]["infrastructure_details"]["lane_count"] == 6
    assert payload["assessment"]["estimated_daily_vehicle_trips"] == 2200
    assert payload["assessment"]["buildout_years"] == 4
    assert payload["assessment"]["analysis_document"]["summary"]
    assert payload["assessment"]["analysis_document"]["sections"]["key_findings"]


def test_text_run_returns_missing_fields_validation(monkeypatch) -> None:
    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        return {
            "infrastructure_type": "airport",
            "project_type": "industrial_facility",
            "planner_summary": "Airport concept with missing dimensions.",
            "infrastructure_details": {
                "terminal_area_sq_m": 18000,
                "daily_vehicle_trips": 3200,
            },
            "missing_fields": ["runway_width_m", "apron_area_sq_m"],
            "assumptions": [],
            "confidence": 0.91,
            "simulation_ready": False,
        }

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/run",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6400, "longitude": -87.5700},
                {"latitude": 41.6540, "longitude": -87.5450},
            ],
            "user_prompt": "I want to build an airport in this area.",
            "mitigation_commitment": "medium",
        },
    )

    assert response.status_code == 422
    assert "missing_fields" in response.json()["detail"]
    assert "runway_width_m" in response.json()["detail"]["missing_fields"]


def test_text_draft_returns_503_when_gemini_unavailable(monkeypatch) -> None:
    def fake_extract_text_plan(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    monkeypatch.setattr(gemini_service, "extract_text_plan", fake_extract_text_plan)

    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "Build a road here for freight movement.",
        },
    )

    assert response.status_code == 503


def test_text_draft_returns_422_for_malformed_gemini_json(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service, "_generate", lambda prompt: "{not-valid-json")

    response = client.post(
        "/api/v1/planning/text/draft",
        json={
            "location": CHICAGO_LOCATION,
            "geometry_points": [
                {"latitude": 41.6401, "longitude": -87.5601},
                {"latitude": 41.6501, "longitude": -87.5401},
            ],
            "user_prompt": "Build a road here for freight movement.",
        },
    )

    assert response.status_code == 422
