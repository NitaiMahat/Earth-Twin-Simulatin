from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_world_returns_seeded_world() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/world")

    assert response.status_code == 200
    payload = response.json()["world"]
    assert payload["world_id"] == "illinois_calumet_corridor_demo"
    assert payload["name"] == "Illinois Calumet Corridor Demo"
    assert len(payload["zones"]) == 4
    assert 0 <= payload["sustainability_score"] <= 100
    allowed_risk_levels = {"low", "medium", "high", "critical"}
    assert all(zone["risk_level"] in allowed_risk_levels for zone in payload["zones"])
    assert all(0 <= zone["sustainability_score"] <= 100 for zone in payload["zones"])


def test_reset_world_restores_seed_values() -> None:
    client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "zone_calumet_habitat_reserve",
            "action_type": "deforestation",
            "intensity": 1.0,
            "duration_years": 2,
        },
    )

    reset_response = client.post("/api/v1/world/reset")
    assert reset_response.status_code == 200

    world = client.get("/api/v1/world").json()["world"]
    forest_zone = next(zone for zone in world["zones"] if zone["zone_id"] == "zone_calumet_habitat_reserve")
    assert forest_zone["tree_cover"] == 82.0
