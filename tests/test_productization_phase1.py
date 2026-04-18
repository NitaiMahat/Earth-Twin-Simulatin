from fastapi.testclient import TestClient

from app.main import app
from app.models.api.requests import AIExplainRequest, ApplyActionRequest, ProjectFutureRequest
from app.models.domain.action import ActionType, AudienceType, SimulationMode
from app.services.action_mapper import action_mapper


client = TestClient(app)


def test_apply_action_request_defaults_mode_to_planning() -> None:
    payload = ApplyActionRequest.model_validate(
        {
            "zone_id": "zone_calumet_habitat_reserve",
            "action_type": "reduce_green_space",
            "intensity": 0.5,
            "duration_years": 2,
        }
    )

    assert payload.mode == SimulationMode.PLANNING


def test_project_request_defaults_mode_to_planning() -> None:
    payload = ProjectFutureRequest.model_validate(
        {
            "base_world_id": "illinois_calumet_corridor_demo",
            "projection_years": 5,
            "actions": [],
        }
    )

    assert payload.mode == SimulationMode.PLANNING


def test_ai_request_defaults_audience_from_mode() -> None:
    learning_payload = AIExplainRequest.model_validate(
        {
            "zone_id": "zone_arterial_infill_corridor",
            "question": "What is happening here?",
            "mode": "learning",
        }
    )
    planning_payload = AIExplainRequest.model_validate(
        {
            "zone_id": "zone_arterial_infill_corridor",
            "question": "What is happening here?",
        }
    )

    assert learning_payload.audience == AudienceType.STUDENT
    assert planning_payload.audience == AudienceType.PLANNER


def test_ai_request_respects_explicit_audience_override() -> None:
    payload = AIExplainRequest.model_validate(
        {
            "zone_id": "zone_arterial_infill_corridor",
            "question": "What is happening here?",
            "mode": "learning",
            "audience": "educator",
        }
    )

    assert payload.audience == AudienceType.EDUCATOR


def test_action_mapper_accepts_product_and_legacy_action_labels() -> None:
    assert action_mapper.normalize_action_type("reduce_green_space") == ActionType.DEFORESTATION
    assert action_mapper.normalize_action_type("restore_ecosystem") == ActionType.RESTORATION
    assert action_mapper.normalize_action_type("traffic_increase") == ActionType.TRAFFIC_INCREASE


def test_zone_responses_include_sustainability_score() -> None:
    client.post("/api/v1/world/reset")
    world_response = client.get("/api/v1/world")
    zone_response = client.get("/api/v1/zones/zone_arterial_infill_corridor")

    assert world_response.status_code == 200
    assert zone_response.status_code == 200

    world_zone = world_response.json()["world"]["zones"][0]
    detail_zone = zone_response.json()["zone"]

    assert 0 <= world_zone["sustainability_score"] <= 100
    assert 0 <= detail_zone["sustainability_score"] <= 100


def test_apply_action_accepts_product_facing_action_type() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "zone_calumet_habitat_reserve",
            "action_type": "reduce_green_space",
            "intensity": 0.5,
            "duration_years": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_action"]["action_type"] == "deforestation"
    assert payload["after"]["tree_cover"] < payload["before"]["tree_cover"]
    assert 0 <= payload["after"]["sustainability_score"] <= 100
