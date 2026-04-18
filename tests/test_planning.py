from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.constants import RiskLevel
from app.main import app
from app.models.domain.planning import MitigationCommitment, PlanVerdict, PlannerProjectType
from app.services.planning_service import planning_service


client = TestClient(app)


def test_get_planning_site_returns_illinois_site_metadata() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/planning/site")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == "illinois_calumet_corridor_demo"
    assert payload["state"] == "Illinois"
    assert len(payload["areas"]) == 3
    assert payload["areas"][0]["baseline_zone_id"].startswith("zone_")
    assert "industrial_facility" in payload["areas"][0]["allowed_project_types"]
    assert len(payload["build_sections"]) == 6


def test_get_build_options_returns_section_specific_fields() -> None:
    response = client.get("/api/v1/planning/build-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == "illinois_calumet_corridor_demo"
    assert len(payload["sections"]) == 6

    airport_section = next(
        section for section in payload["sections"] if section["infrastructure_type"] == "airport"
    )
    field_names = [field["field_name"] for field in airport_section["fields"]]

    assert "runway_length_m" in field_names
    assert "runway_width_m" in field_names
    assert "terminal_area_sq_m" in field_names
    assert "apron_area_sq_m" in field_names


def test_assess_proposal_returns_scorecards_and_simulation_inputs() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "site_id": "illinois_calumet_corridor_demo",
            "area_id": "calumet_industrial_strip",
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
    assert payload["submitted_plan"]["verdict"] in {"recommended", "conditional", "not_recommended"}
    assert payload["mitigated_plan"]["verdict"] in {"recommended", "conditional", "not_recommended"}
    assert payload["recommended_option"] in {"submitted_plan", "mitigated_plan"}
    assert payload["simulation_inputs"]["projection_years"] == 5
    assert payload["simulation_inputs"]["footprint_bucket"] == "large"
    assert payload["simulation_inputs"]["traffic_bucket"] == "high"
    assert len(payload["simulation_inputs"]["submitted_actions"]) == 2
    assert len(payload["simulation_inputs"]["mitigated_actions"]) >= 3
    assert payload["simulation_inputs"]["submitted_actions"][0]["normalized_action_type"] == "pollution_spike"


def test_assess_proposal_accepts_infrastructure_specific_airport_details() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "site_id": "illinois_calumet_corridor_demo",
            "area_id": "calumet_industrial_strip",
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


def test_assess_proposal_rejects_unknown_site_and_disallowed_project_type() -> None:
    client.post("/api/v1/world/reset")
    wrong_site = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "site_id": "wrong_site",
            "area_id": "calumet_industrial_strip",
            "project_type": "industrial_facility",
            "footprint_acres": 20,
            "estimated_daily_vehicle_trips": 900,
            "buildout_years": 3,
            "mitigation_commitment": "medium",
        },
    )
    wrong_project = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "site_id": "illinois_calumet_corridor_demo",
            "area_id": "river_buffer_redevelopment",
            "project_type": "industrial_facility",
            "footprint_acres": 20,
            "estimated_daily_vehicle_trips": 900,
            "buildout_years": 3,
            "mitigation_commitment": "medium",
        },
    )

    assert wrong_site.status_code == 422
    assert wrong_project.status_code == 422


def test_assess_proposal_validates_numeric_ranges() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/planning/proposals/assess",
        json={
            "site_id": "illinois_calumet_corridor_demo",
            "area_id": "arterial_infill_corridor",
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
            "site_id": "illinois_calumet_corridor_demo",
            "area_id": "calumet_industrial_strip",
            "infrastructure_type": "airport",
            "infrastructure_details": {
                "runway_length_m": 2400,
                "daily_vehicle_trips": 3200
            },
            "mitigation_commitment": "medium"
        },
    )

    assert response.status_code == 422


def test_planning_service_maps_project_type_and_mitigation_commitment_deterministically() -> None:
    client.post("/api/v1/world/reset")
    low_commitment = planning_service.assess_proposal(
        site_id="illinois_calumet_corridor_demo",
        area_id="arterial_infill_corridor",
        project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        infrastructure_type=None,
        infrastructure_details={},
        footprint_acres=12,
        estimated_daily_vehicle_trips=1500,
        buildout_years=3,
        mitigation_commitment=MitigationCommitment.LOW,
    )
    high_commitment = planning_service.assess_proposal(
        site_id="illinois_calumet_corridor_demo",
        area_id="arterial_infill_corridor",
        project_type=PlannerProjectType.ROADWAY_LOGISTICS_EXPANSION,
        infrastructure_type=None,
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
