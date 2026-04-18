from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_zones_returns_all_zones() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/zones")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 4
    assert len(payload["zones"]) == 4


def test_get_single_zone_returns_zone_details() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/zones/zone_arterial_infill_corridor")

    assert response.status_code == 200
    body = response.json()
    payload = body["zone"]
    assert payload["zone_id"] == "zone_arterial_infill_corridor"
    assert payload["type"] == "city"
    assert payload["risk_level"] in {"low", "medium", "high", "critical"}
    assert 0 <= payload["sustainability_score"] <= 100
    assert isinstance(body["risk_summary"], str)
    assert len(body["top_drivers"]) >= 1
    assert isinstance(body["recommended_focus"], str)
