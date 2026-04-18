"""Session-scoped fixtures that make Gemini API calls once per test session.

Live tests share these cached responses instead of each making their own call,
keeping the total number of API calls low enough for free-tier rate limits.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)

_ZONE_ID = "zone_calumet_industrial_strip"
_GOAL = "Reduce pollution but keep traffic flowing"

_INITIAL_METRICS = {
    "zone_id": _ZONE_ID,
    "name": "Calumet Industrial Strip",
    "type": "industrial",
    "tree_cover": 8.0,
    "biodiversity_score": 31.0,
    "pollution_level": 73.0,
    "traffic_level": 61.0,
    "temperature": 29.3,
    "ecosystem_health": 34.0,
    "risk_level": "critical",
    "sustainability_score": 22.5,
}


@pytest.fixture(scope="session")
def gemini_actions() -> list[dict]:
    """One goal-to-actions call shared across the whole test session."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    resp = _client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": _GOAL, "zone_id": _ZONE_ID},
    )
    assert resp.status_code == 200, f"goal-to-actions fixture failed: {resp.text}"
    return resp.json()["actions"]


@pytest.fixture(scope="session")
def simulation_result(gemini_actions: list[dict]) -> dict:
    """One simulation/project call shared across the whole test session."""
    resp = _client.post(
        "/api/v1/simulation/project",
        json={
            "base_world_id": "illinois_calumet_corridor_demo",
            "projection_years": 5,
            "mode": "planning",
            "actions": [
                {
                    "zone_id": _ZONE_ID,
                    "action_type": a["action_type"],
                    "intensity": a["intensity"],
                    "duration_years": a["duration_years"],
                }
                for a in gemini_actions
            ],
        },
    )
    assert resp.status_code == 200, f"simulation fixture failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope="session")
def projected_zone(simulation_result: dict) -> dict:
    """The post-simulation state of the target zone."""
    zone = next(
        (z for z in simulation_result["projected_zones"] if z["zone_id"] == _ZONE_ID),
        {},
    )
    assert zone, "Target zone not found in simulation result"
    return zone


@pytest.fixture(scope="session")
def gemini_analysis(gemini_actions: list[dict], projected_zone: dict,
                    simulation_result: dict) -> str:
    """One suggest-improvements call shared across the whole test session."""
    resp = _client.post(
        "/api/v1/ai/suggest-improvements",
        json={
            "goal": _GOAL,
            "zone_id": _ZONE_ID,
            "zone_name": "Calumet Industrial Strip",
            "actions": gemini_actions,
            "initial_metrics": _INITIAL_METRICS,
            "final_metrics": projected_zone,
            "projection_years": 5,
            "sustainability_score": simulation_result["sustainability_score"],
            "overall_outlook": simulation_result.get("overall_outlook", "mixed"),
        },
    )
    assert resp.status_code == 200, f"suggest-improvements fixture failed: {resp.text}"
    return resp.json()["analysis"]
