from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.provider_cache_repository import ProviderCacheSnapshot
from app.services.public_baseline_service import public_baseline_service


client = TestClient(app)


def test_get_world_returns_seeded_world() -> None:
    client.post("/api/v1/world/reset")
    response = client.get("/api/v1/world")

    assert response.status_code == 200
    payload = response.json()["world"]
    assert payload["world_id"] == "global_continental_baseline"
    assert payload["name"] == "Earth Twin Global Continents"
    assert payload["baseline_mode"] == "dynamic_public"
    assert len(payload["zones"]) == 7
    assert 0 <= payload["sustainability_score"] <= 100
    allowed_risk_levels = {"low", "medium", "high", "critical"}
    assert all(zone["risk_level"] in allowed_risk_levels for zone in payload["zones"])
    assert all(0 <= zone["sustainability_score"] <= 100 for zone in payload["zones"])
    assert any(zone["zone_id"] == "continent_africa" for zone in payload["zones"])
    assert any(zone["zone_id"] == "continent_asia" for zone in payload["zones"])


def test_reset_world_restores_seed_values() -> None:
    client.post(
        "/api/v1/simulation/apply",
        json={
            "zone_id": "continent_south_america",
            "action_type": "deforestation",
            "intensity": 1.0,
            "duration_years": 2,
        },
    )

    reset_response = client.post("/api/v1/world/reset")
    assert reset_response.status_code == 200

    world = client.get("/api/v1/world").json()["world"]
    continent = next(zone for zone in world["zones"] if zone["zone_id"] == "continent_south_america")
    assert 0 <= continent["tree_cover"] <= 100
    assert continent["scope"] == "continent"


def test_reverse_geocode_uses_cache_for_same_coordinate(monkeypatch) -> None:
    public_baseline_service._cache.clear()
    call_count = {"count": 0}

    def fake_request(url: str, params: dict[str, object]) -> dict[str, object]:
        call_count["count"] += 1
        return {
            "address": {
                "country_code": "us",
                "country": "United States",
                "state": "Illinois",
                "city": "Chicago",
            }
        }

    monkeypatch.setattr(public_baseline_service, "_request_json", fake_request)

    first = public_baseline_service._reverse_geocode(41.8781, -87.6298)
    second = public_baseline_service._reverse_geocode(41.87811, -87.62981)

    assert first["address"]["country"] == "United States"
    assert second["address"]["state"] == "Illinois"
    assert call_count["count"] == 1


def test_cache_get_hydrates_from_persistent_cache(monkeypatch) -> None:
    public_baseline_service._cache.clear()

    class FakePersistentCache:
        def get(self, key: str) -> ProviderCacheSnapshot | None:
            if key != "reverse_geocode:41.878,-87.630":
                return None
            return ProviderCacheSnapshot(
                key=key,
                value={"address": {"country": "United States"}},
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )

        def set(self, key: str, value: object, ttl_seconds: int) -> bool:
            return True

    monkeypatch.setattr(public_baseline_service, "_persistent_cache", FakePersistentCache())

    cached_value = public_baseline_service._cache_get("reverse_geocode:41.878,-87.630")

    assert cached_value == {"address": {"country": "United States"}}
    assert "reverse_geocode:41.878,-87.630" in public_baseline_service._cache


def test_cache_set_writes_through_to_persistent_cache(monkeypatch) -> None:
    public_baseline_service._cache.clear()
    captured: dict[str, object] = {}

    class FakePersistentCache:
        def get(self, key: str) -> ProviderCacheSnapshot | None:
            return None

        def set(self, key: str, value: object, ttl_seconds: int) -> bool:
            captured["key"] = key
            captured["value"] = value
            captured["ttl_seconds"] = ttl_seconds
            return True

    monkeypatch.setattr(public_baseline_service, "_persistent_cache", FakePersistentCache())

    payload = {"current": {"temperature_2m": 22.4}}
    stored = public_baseline_service._cache_set("weather:41.878,-87.630", payload, ttl_seconds=120)

    assert stored == payload
    assert captured == {
        "key": "weather:41.878,-87.630",
        "value": payload,
        "ttl_seconds": 120,
    }
