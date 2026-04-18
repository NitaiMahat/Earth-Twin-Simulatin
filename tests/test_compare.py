from fastapi.testclient import TestClient

from app.core.constants import RiskLevel
from app.main import app
from app.models.domain.action import SimulationMode
from app.models.domain.simulation import ComparedScenarioResult, CompactZoneSummary
from app.services.simulation_engine import simulation_engine


client = TestClient(app)


def test_compare_endpoint_returns_recommendation_and_tradeoffs() -> None:
    client.post("/api/v1/world/reset")
    base_world = client.get("/api/v1/world").json()["world"]
    response = client.post(
        "/api/v1/simulation/compare",
        json={
            "base_world_id": "global_continental_baseline",
            "projection_years": 5,
            "mode": "planning",
            "scenarios": [
                {
                    "name": "Road Expansion",
                    "actions": [
                        {
                            "zone_id": "continent_north_america",
                            "action_type": "expand_roadway",
                            "intensity": 0.8,
                            "duration_years": 3,
                        }
                    ],
                },
                {
                    "name": "Transit + Parks",
                    "actions": [
                        {
                            "zone_id": "continent_north_america",
                            "action_type": "improve_public_transit",
                            "intensity": 0.8,
                            "duration_years": 3,
                        },
                        {
                            "zone_id": "continent_north_america",
                            "action_type": "add_urban_park",
                            "intensity": 0.5,
                            "duration_years": 2,
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "planning"
    assert payload["projection_years"] == 5
    assert len(payload["scenarios"]) == 2
    assert payload["recommended_scenario"] == "Transit + Parks"
    assert len(payload["key_tradeoffs"]) >= 1
    assert isinstance(payload["comparison_summary_text"], str)
    assert all("sustainability_score" in scenario for scenario in payload["scenarios"])
    assert all("highest_risk_zone" in scenario for scenario in payload["scenarios"])

    current_world = client.get("/api/v1/world").json()["world"]
    assert current_world["current_year"] == base_world["current_year"]
    assert current_world["sustainability_score"] == base_world["sustainability_score"]
    current_city = next(
        zone for zone in current_world["zones"] if zone["zone_id"] == "continent_north_america"
    )
    base_city = next(zone for zone in base_world["zones"] if zone["zone_id"] == "continent_north_america")
    assert current_city["traffic_level"] == base_city["traffic_level"]


def test_compare_rejects_unsupported_action_type() -> None:
    client.post("/api/v1/world/reset")
    response = client.post(
        "/api/v1/simulation/compare",
        json={
            "base_world_id": "global_continental_baseline",
            "projection_years": 5,
            "scenarios": [
                {
                    "name": "Bad A",
                    "actions": [
                        {
                            "zone_id": "continent_north_america",
                            "action_type": "volcano_mode",
                            "intensity": 0.8,
                            "duration_years": 3,
                        }
                    ],
                },
                {
                    "name": "Bad B",
                    "actions": [
                        {
                            "zone_id": "continent_north_america",
                            "action_type": "expand_roadway",
                            "intensity": 0.8,
                            "duration_years": 3,
                        }
                    ],
                },
            ],
        },
    )

    assert response.status_code == 422


def test_recommended_scenario_tie_break_prefers_lower_risk_then_temperature() -> None:
    scenarios = [
        ComparedScenarioResult(
            name="Scenario A",
            summary="A",
            summary_text="A",
            highest_risk_zone=CompactZoneSummary(
                zone_id="zone_a",
                name="Zone A",
                risk_level=RiskLevel.HIGH,
                sustainability_score=40,
            ),
            avg_biodiversity_drop=2.0,
            avg_temperature_change=0.7,
            sustainability_score=60.0,
            overall_outlook="mixed",
            recommended_focus="Focus A",
        ),
        ComparedScenarioResult(
            name="Scenario B",
            summary="B",
            summary_text="B",
            highest_risk_zone=CompactZoneSummary(
                zone_id="zone_b",
                name="Zone B",
                risk_level=RiskLevel.MEDIUM,
                sustainability_score=45,
            ),
            avg_biodiversity_drop=3.0,
            avg_temperature_change=1.0,
            sustainability_score=60.0,
            overall_outlook="mixed",
            recommended_focus="Focus B",
        ),
    ]

    recommended = simulation_engine.select_recommended_scenario(scenarios)

    assert recommended == "Scenario B"
