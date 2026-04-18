from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_education_routes_remain_open_without_auth() -> None:
    scenarios = client.get("/api/v1/education/scenarios/templates")
    explain = client.post(
        "/api/v1/education/ai/explain",
        json={
            "zone_id": "zone_arterial_infill_corridor",
            "question": "What is happening here?",
            "context": "Open learning view."
        },
    )

    assert scenarios.status_code == 200
    assert explain.status_code == 200
    assert scenarios.json()["count"] >= 1
    assert explain.json()["mode"] == "learning"


def test_education_project_endpoint_forces_learning_mode() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/education/simulation/project",
        json={
            "base_world_id": "illinois_calumet_corridor_demo",
            "projection_years": 4,
            "mode": "planning",
            "actions": [
                {
                    "zone_id": "zone_arterial_infill_corridor",
                    "action_type": "increase_traffic",
                    "intensity": 0.7,
                    "duration_years": 2
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "learning"
    assert payload["projection_years"] == 4
