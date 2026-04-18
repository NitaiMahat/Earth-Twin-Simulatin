from fastapi.testclient import TestClient

from app.api.deps.supabase_auth import get_current_user
from app.main import app
from app.models.domain.auth import AuthenticatedUser
from app.services.project_snapshot_service import project_snapshot_service

client = TestClient(app)

CHICAGO_LOCATION = {
    "latitude": 41.8781,
    "longitude": -87.6298,
    "label": "Chicago Test Location",
    "country_code": "USA",
}


class FakeProjectRepository:
    def __init__(self) -> None:
        self.enabled = True
        self.records: dict[str, dict] = {}

    def ensure_ready(self) -> bool:
        return True

    def create_project(self, record: dict) -> dict | None:
        created = {
            **record,
            "created_at": "2026-04-18T20:00:00+00:00",
            "updated_at": "2026-04-18T20:00:00+00:00",
        }
        self.records[record["project_id"]] = created
        return created

    def list_projects(self, user_id: str) -> list[dict]:
        return [record for record in self.records.values() if record["user_id"] == user_id]

    def get_project(self, user_id: str, project_id: str) -> dict | None:
        record = self.records.get(project_id)
        if record is None or record["user_id"] != user_id:
            return None
        return record

    def update_report(self, user_id: str, project_id: str, report_payload: dict) -> dict | None:
        record = self.get_project(user_id, project_id)
        if record is None:
            return None
        updated = {
            **record,
            "latest_report_payload": report_payload,
            "updated_at": report_payload["updated_at"],
        }
        self.records[project_id] = updated
        return updated


def _override_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="user-123",
        email="planner@example.com",
        role="authenticated",
        org_id="org-1",
    )


def setup_function() -> None:
    project_snapshot_service._repository = FakeProjectRepository()
    app.dependency_overrides[get_current_user] = _override_user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_auth_me_returns_current_user() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-123",
        "email": "planner@example.com",
        "role": "authenticated",
        "org_id": "org-1",
    }


def test_save_and_list_my_projects() -> None:
    save_response = client.post(
        "/api/v1/my-projects",
        json={
            "project_name": "Chicago Cargo Airport",
            "location": CHICAGO_LOCATION,
            "infrastructure_type": "airport",
            "infrastructure_details": {
                "runway_length_m": 2400,
                "runway_width_m": 45,
                "terminal_area_sq_m": 18000,
                "apron_area_sq_m": 42000,
                "daily_vehicle_trips": 3200,
                "construction_years": 5,
            },
            "mitigation_commitment": "medium",
            "planner_notes": "Regional cargo airport expansion.",
        },
    )

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["project_name"] == "Chicago Cargo Airport"
    assert saved_payload["assessment"]["location_context"]["label"] == "Chicago Test Location"
    assert saved_payload["assessment"]["recommended_option"] in {"submitted_plan", "mitigated_plan"}

    list_response = client.get("/api/v1/my-projects")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["projects"][0]["project_name"] == "Chicago Cargo Airport"
    assert payload["projects"][0]["latest_report"]["pdf_url"] is None


def test_update_project_report_metadata() -> None:
    save_response = client.post(
        "/api/v1/my-projects",
        json={
            "project_name": "Chicago Solar Study",
            "location": CHICAGO_LOCATION,
            "project_type": "mixed_use_redevelopment",
            "footprint_acres": 25,
            "estimated_daily_vehicle_trips": 900,
            "buildout_years": 4,
            "mitigation_commitment": "high",
        },
    )
    project_id = save_response.json()["project_id"]

    update_response = client.patch(
        f"/api/v1/my-projects/{project_id}/report",
        json={
            "ai_analysis": "Mitigated option meaningfully lowers pollution pressure.",
            "pdf_url": "https://storage.example.com/reports/chicago-solar.pdf",
            "pdf_filename": "chicago-solar.pdf",
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["latest_report"]["ai_analysis"] == "Mitigated option meaningfully lowers pollution pressure."
    assert payload["latest_report"]["pdf_filename"] == "chicago-solar.pdf"
    assert payload["latest_report"]["pdf_url"] == "https://storage.example.com/reports/chicago-solar.pdf"
