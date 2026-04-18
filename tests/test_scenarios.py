from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_scenario_templates_returns_all_templates_and_supports_mode_filter() -> None:
    response = client.get("/api/v1/scenarios/templates")
    learning_response = client.get("/api/v1/scenarios/templates?mode=learning")

    assert response.status_code == 200
    assert learning_response.status_code == 200

    payload = response.json()
    learning_payload = learning_response.json()
    assert payload["count"] == 8
    assert learning_payload["count"] == 4
    assert all(template["mode"] == "learning" for template in learning_payload["templates"])


def test_get_scenario_template_returns_template_detail() -> None:
    response = client.get("/api/v1/scenarios/templates/road_expansion_plan")

    assert response.status_code == 200
    template = response.json()["template"]
    assert template["template_id"] == "road_expansion_plan"
    assert template["objective"]
    assert template["product_focus"]


def test_get_scenario_template_rejects_unknown_template_id() -> None:
    response = client.get("/api/v1/scenarios/templates/template_missing")

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_run_template_returns_projection_without_mutating_live_world() -> None:
    client.post("/api/v1/world/reset")
    base_world = client.get("/api/v1/world").json()["world"]

    response = client.post("/api/v1/scenarios/templates/green_restoration_plan/run", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["template_id"] == "green_restoration_plan"
    assert payload["template_name"] == "Green Restoration Plan"
    assert payload["projection_years"] == 6
    assert payload["summary"]
    assert payload["summary_text"]
    assert len(payload["projected_zones"]) == 4
    assert 0 <= payload["sustainability_score"] <= 100

    current_world = client.get("/api/v1/world").json()["world"]
    assert current_world["current_year"] == base_world["current_year"]
    assert current_world["sustainability_score"] == base_world["sustainability_score"]


def test_run_template_rejects_unknown_template_id() -> None:
    response = client.post("/api/v1/scenarios/templates/template_missing/run", json={})

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]
