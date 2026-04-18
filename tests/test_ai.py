from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ai_explain_returns_planning_friendly_explanation() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/ai/explain",
        json={
            "zone_id": "continent_asia",
            "context": "Global infrastructure planning context after several pollution events.",
            "question": "Why is this continent under pressure?",
            "mode": "planning",
            "audience": "municipality",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Asia" in payload["answer"]
    assert "sustainability score" in payload["answer"].lower()
    assert 3 <= len(payload["bullets"]) <= 5
    assert 2 <= len(payload["recommended_actions"]) <= 4
    assert payload["tone"] == "decision-support"
    assert payload["audience"] == "municipality"
    assert payload["mode"] == "planning"
    assert not payload["recommended_actions"][0].startswith("Try this next:")


def test_ai_explain_returns_learning_friendly_explanation_with_default_audience() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/ai/explain",
        json={
            "zone_id": "continent_north_america",
            "context": "Traffic and emissions increased after a major infrastructure expansion.",
            "question": "What is likely driving the current risk?",
            "mode": "learning",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tone"] == "educational"
    assert payload["audience"] == "student"
    assert payload["mode"] == "learning"
    assert "sustainability score" in payload["answer"].lower()
    assert "shows how" in payload["answer"].lower() or "when tree cover" in payload["bullets"][1].lower()
    assert any(action.startswith("Try this next:") for action in payload["recommended_actions"])


def test_ai_explain_rejects_unknown_zone_id() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/ai/explain",
        json={
            "zone_id": "zone_missing",
            "context": "Global planning context.",
            "question": "Why is this continent at risk?",
        },
    )

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]
