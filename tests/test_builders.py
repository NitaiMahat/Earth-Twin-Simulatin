from fastapi.testclient import TestClient

from app.main import app
from app.repositories.builder_project_repository import builder_project_repository


client = TestClient(app)

BUILDER_HEADERS = {"Authorization": "Bearer builder-demo-token"}
OTHER_BUILDER_HEADERS = {"Authorization": "Bearer builder-other-org-token"}
NON_BUILDER_HEADERS = {"Authorization": "Bearer education-demo-token"}


def setup_function() -> None:
    builder_project_repository.reset()
    client.post("/api/v1/world/reset")


def _create_builder_project() -> str:
    response = client.post(
        "/api/v1/builders/projects",
        headers=BUILDER_HEADERS,
        json={
            "project_name": "Calumet runway plan",
            "site_id": "usa_calumet_builder_site",
            "area_id": "calumet_industrial_strip",
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
            "mitigation_commitment": "medium",
            "planner_notes": "Builder runway project."
        },
    )

    assert response.status_code == 201
    return response.json()["project_id"]


def test_builder_routes_reject_unauthenticated_users() -> None:
    response = client.get("/api/v1/builders/sites")

    assert response.status_code == 401


def test_builder_routes_reject_authenticated_non_builder_users() -> None:
    response = client.get("/api/v1/builders/sites", headers=NON_BUILDER_HEADERS)

    assert response.status_code == 403


def test_builder_sites_return_only_usa_managed_sites() -> None:
    response = client.get("/api/v1/builders/sites", headers=BUILDER_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["country"] == "USA"


def test_builder_site_area_endpoint_returns_backend_managed_areas() -> None:
    response = client.get("/api/v1/builders/sites/usa_calumet_builder_site/areas", headers=BUILDER_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["country"] == "USA"
    assert len(payload["areas"]) == 3
    assert payload["areas"][0]["baseline_zone_id"].startswith("zone_")


def test_builder_project_creation_persists_full_snapshot_inputs() -> None:
    project_id = _create_builder_project()

    detail = client.get(f"/api/v1/builders/projects/{project_id}", headers=BUILDER_HEADERS)

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["project_name"] == "Calumet runway plan"
    assert payload["proposal"]["infrastructure_type"] == "airport"
    assert len(payload["proposal"]["geometry_points"]) == 2
    assert payload["latest_report"] is None


def test_builder_project_simulation_creates_report_and_history_entry() -> None:
    project_id = _create_builder_project()

    simulate = client.post(f"/api/v1/builders/projects/{project_id}/simulate", headers=BUILDER_HEADERS, json={})
    report = client.get(f"/api/v1/builders/projects/{project_id}/report", headers=BUILDER_HEADERS)
    history = client.get(f"/api/v1/builders/projects/{project_id}/history", headers=BUILDER_HEADERS)

    assert simulate.status_code == 200
    assert report.status_code == 200
    assert history.status_code == 200
    assert report.json()["report"]["submitted_plan"]["verdict"] in {"recommended", "conditional", "not_recommended"}
    assert report.json()["report"]["geometry_summary"]["selection_mode"] == "line"
    assert history.json()["count"] == 1
    assert history.json()["entries"][0]["report"]["recommended_option"] in {"submitted_plan", "mitigated_plan"}


def test_builder_project_list_returns_saved_projects_for_builder_org() -> None:
    _create_builder_project()

    response = client.get("/api/v1/builders/projects", headers=BUILDER_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["projects"][0]["project_name"] == "Calumet runway plan"


def test_builder_project_access_rejects_other_organizations() -> None:
    project_id = _create_builder_project()

    response = client.get(f"/api/v1/builders/projects/{project_id}", headers=OTHER_BUILDER_HEADERS)

    assert response.status_code == 403
