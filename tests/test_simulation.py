from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_apply_action_returns_frontend_friendly_before_and_after_payload() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_south_america",
            "action_type": "deforestation",
            "intensity": 0.5,
            "duration_years": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["zone_id"] == "continent_south_america"
    assert payload["requested_action_type"] == "deforestation"
    assert payload["normalized_action_type"] == "deforestation"
    assert payload["mode"] == "planning"
    assert payload["applied_action"]["action_type"] == "deforestation"
    assert payload["applied_action"]["intensity"] == 0.5
    assert payload["applied_action"]["duration_years"] == 2
    assert payload["after"]["tree_cover"] < payload["before"]["tree_cover"]
    assert payload["after"]["biodiversity_score"] < payload["before"]["biodiversity_score"]
    assert payload["delta"]["temperature"] > 0
    assert payload["delta"]["tree_cover"] < 0
    assert payload["deltas"] == payload["delta"]
    assert len(payload["derived_effects"]) >= 1
    assert payload["risk_level"] == payload["after"]["risk_level"]
    assert payload["sustainability_score"] == payload["after"]["sustainability_score"]
    assert isinstance(payload["summary_text"], str)
    assert len(payload["top_drivers"]) >= 1


def test_apply_action_mutates_current_in_memory_world_state() -> None:
    client.post("/api/v1/world/reset")
    before_zone = client.get("/api/v1/zones/continent_north_america").json()["zone"]

    apply_response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_north_america",
            "action_type": "traffic_increase",
            "intensity": 0.8,
            "duration_years": 2,
        },
    )

    assert apply_response.status_code == 200

    after_zone = client.get("/api/v1/zones/continent_north_america").json()["zone"]
    assert after_zone["traffic_level"] > before_zone["traffic_level"]
    assert after_zone["pollution_level"] > before_zone["pollution_level"]


def test_apply_action_rejects_unsupported_action_type() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_south_america",
            "action_type": "volcano_mode",
            "intensity": 0.5,
            "duration_years": 2,
        },
    )

    assert response.status_code == 422


def test_apply_action_validates_intensity_range() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_south_america",
            "action_type": "deforestation",
            "intensity": 1.5,
            "duration_years": 2,
        },
    )

    assert response.status_code == 422


def test_apply_action_validates_duration_years_range() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_south_america",
            "action_type": "deforestation",
            "intensity": 0.5,
            "duration_years": 0,
        },
    )

    assert response.status_code == 422


def test_apply_action_rejects_unknown_zone_id_from_service_layer() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "zone_unknown",
            "action_type": "deforestation",
            "intensity": 0.5,
            "duration_years": 2,
        },
    )

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_project_future_returns_projection_summary_without_mutating_live_world() -> None:
    client.post("/api/v1/world/reset")
    base_world = client.get("/api/v1/world").json()["world"]

    response = client.post(
        "/api/v1/simulation/project",
        json={
            "base_world_id": "global_continental_baseline",
            "projection_years": 5,
            "mode": "learning",
            "actions": [
                {
                    "zone_id": "continent_oceania",
                    "action_type": "pollution_spike",
                    "intensity": 0.8,
                    "duration_years": 3,
                },
                {
                    "zone_id": "continent_south_america",
                    "action_type": "restoration",
                    "intensity": 0.4,
                    "duration_years": 2,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["projection_years"] == 5
    assert payload["mode"] == "learning"
    assert isinstance(payload["summary"], str)
    assert isinstance(payload["summary_text"], str)
    assert len(payload["projected_zones"]) == 7
    assert payload["highest_risk_zone"] is not None
    assert "avg_biodiversity_drop" in payload
    assert "avg_temperature_change" in payload
    assert "sustainability_score" in payload
    assert "overall_outlook" in payload
    assert "recommended_focus" in payload
    assert isinstance(payload["highest_risk_zone_top_drivers"], list)

    current_world = client.get("/api/v1/world").json()["world"]
    assert current_world["current_year"] == base_world["current_year"]

    current_coastal = next(
        zone for zone in current_world["zones"] if zone["zone_id"] == "continent_oceania"
    )
    base_coastal = next(zone for zone in base_world["zones"] if zone["zone_id"] == "continent_oceania")
    assert current_coastal["pollution_level"] == base_coastal["pollution_level"]


def test_project_future_rejects_unknown_world_id() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/project",
        json={
            "base_world_id": "world_missing",
            "projection_years": 5,
            "actions": [],
        },
    )

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_project_future_validates_action_shape() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/project",
        json={
            "base_world_id": "global_continental_baseline",
            "projection_years": 5,
            "actions": [
                {
                    "zone_id": "continent_oceania",
                    "action_type": "pollution_spike",
                    "intensity": 1.4,
                    "duration_years": 3,
                }
            ],
        },
    )

    assert response.status_code == 422


def test_project_future_accepts_product_facing_action_types() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/project",
        json={
            "base_world_id": "global_continental_baseline",
            "projection_years": 5,
            "actions": [
                {
                    "zone_id": "continent_north_america",
                    "action_type": "improve_public_transit",
                    "intensity": 0.8,
                    "duration_years": 3,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["projected_zones"][1]["sustainability_score"] >= 0
