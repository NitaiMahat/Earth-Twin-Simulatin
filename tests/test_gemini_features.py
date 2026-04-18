"""Tests for Gemini AI and PDF report endpoints.

Sections
--------
1. Shared constants
2. /api/v1/simulation/report  — PDF generation (no Gemini needed when ai_analysis provided)
3. /api/v1/ai/goal-to-actions — input validation (no key) + response shape (uses fixture)
4. /api/v1/ai/suggest-improvements — input validation (no key) + analysis quality (uses fixture)
5. End-to-end integration — exercises the full pipeline using session fixtures

Live Gemini calls are made exactly 3 times per test session via session-scoped fixtures
in conftest.py: once for goal-to-actions, once for simulation, once for suggest-improvements.
All live tests consume those cached results.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_HAS_KEY = bool(os.environ.get("GEMINI_API_KEY"))
_SKIP_NO_KEY = pytest.mark.skipif(not _HAS_KEY, reason="GEMINI_API_KEY not set")
_SKIP_HAS_KEY = pytest.mark.skipif(_HAS_KEY, reason="GEMINI_API_KEY is set — error-path test irrelevant")
_LIVE = pytest.mark.live_gemini  # combined marker applied to all live-API tests

ZONE_ID = "continent_asia"

INITIAL_METRICS = {
    "zone_id": ZONE_ID,
    "name": "Asia",
    "type": "continent",
    "tree_cover": 28.0,
    "biodiversity_score": 46.0,
    "pollution_level": 62.0,
    "traffic_level": 68.0,
    "temperature": 26.8,
    "ecosystem_health": 43.0,
    "risk_level": "high",
    "sustainability_score": 34.5,
}

FINAL_METRICS = {
    **INITIAL_METRICS,
    "pollution_level": 55.0,
    "traffic_level": 48.0,
    "temperature": 28.5,
    "ecosystem_health": 42.0,
    "sustainability_score": 33.0,
    "risk_level": "high",
}

ACTIONS = [
    {"action_type": "improve_public_transit", "intensity": 0.7, "duration_years": 3},
    {"action_type": "add_urban_park", "intensity": 0.5, "duration_years": 2},
]

SAMPLE_ANALYSIS = (
    "EXECUTIVE SUMMARY\n"
    "The simulation shows measurable improvement in air quality.\n\n"
    "KEY FINDINGS\n"
    "* Pollution dropped from 73 to 55.\n"
    "* Traffic reduced by 13 points.\n\n"
    "IMPROVEMENT RECOMMENDATIONS\n"
    "1. Expand park coverage.\n"
    "2. Add cycling lanes.\n\n"
    "LONG-TERM OUTLOOK\n"
    "Continued investment will move zone from high to medium risk by 2040."
)

_REPORT_BASE = dict(
    goal="Reduce pollution but keep traffic flowing",
    zone_name="Asia",
    zone_type="continent",
    actions=ACTIONS,
    initial_metrics=INITIAL_METRICS,
    final_metrics=FINAL_METRICS,
    projection_years=5,
    sustainability_score=33.0,
    overall_outlook="moderate",
    ai_analysis=SAMPLE_ANALYSIS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  /api/v1/simulation/report — PDF generation (always runnable)
# ═══════════════════════════════════════════════════════════════════════════════

def test_report_returns_pdf_magic_bytes() -> None:
    resp = client.post("/api/v1/simulation/report", json=_REPORT_BASE)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_content_type_is_pdf() -> None:
    resp = client.post("/api/v1/simulation/report", json=_REPORT_BASE)
    assert resp.headers["content-type"] == "application/pdf"


def test_report_content_disposition_is_attachment() -> None:
    resp = client.post("/api/v1/simulation/report", json=_REPORT_BASE)
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert ".pdf" in disposition


def test_report_pdf_is_substantial_size() -> None:
    resp = client.post("/api/v1/simulation/report", json=_REPORT_BASE)
    assert len(resp.content) > 2000


def test_report_works_with_empty_actions() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "actions": []})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_works_with_single_action() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "actions": [ACTIONS[0]]})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_works_with_all_zone_types() -> None:
    for zone_type in ("wetland", "city", "industrial", "coastal"):
        resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "zone_type": zone_type})
        assert resp.status_code == 200, f"Failed for zone_type={zone_type}"


def test_report_works_with_extreme_metrics() -> None:
    extreme_initial = {**INITIAL_METRICS, "tree_cover": 0.0, "pollution_level": 100.0,
                       "sustainability_score": 0.0, "risk_level": "critical"}
    extreme_final = {**FINAL_METRICS, "tree_cover": 100.0, "pollution_level": 0.0,
                     "sustainability_score": 100.0, "risk_level": "low"}
    payload = {**_REPORT_BASE, "initial_metrics": extreme_initial,
               "final_metrics": extreme_final, "sustainability_score": 100.0}
    resp = client.post("/api/v1/simulation/report", json=payload)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_accepts_maximum_projection_years() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "projection_years": 50})
    assert resp.status_code == 200


@_SKIP_HAS_KEY
def test_report_returns_503_when_analysis_missing_and_no_key() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "ai_analysis": ""})
    assert resp.status_code == 503


def test_report_rejects_missing_goal() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "goal"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_zone_name() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "zone_name"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_actions() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "actions"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_initial_metrics() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "initial_metrics"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_final_metrics() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "final_metrics"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_sustainability_score() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "sustainability_score"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_missing_overall_outlook() -> None:
    payload = {k: v for k, v in _REPORT_BASE.items() if k != "overall_outlook"}
    assert client.post("/api/v1/simulation/report", json=payload).status_code == 422


def test_report_rejects_projection_years_above_max() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "projection_years": 51})
    assert resp.status_code == 422


def test_report_rejects_projection_years_below_min() -> None:
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "projection_years": 0})
    assert resp.status_code == 422


def test_report_works_with_actions_missing_optional_fields() -> None:
    """PDF service uses .get() so actions with only action_type should not crash."""
    minimal_actions = [{"action_type": "add_urban_park"}, {"action_type": "improve_public_transit"}]
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "actions": minimal_actions})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_works_with_empty_metrics_dicts() -> None:
    """PDF service falls back to .get() defaults when metrics keys are absent."""
    resp = client.post(
        "/api/v1/simulation/report",
        json={**_REPORT_BASE, "initial_metrics": {}, "final_metrics": {}},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_works_with_ai_analysis_missing_section_headers() -> None:
    """PDF report should render even if analysis text has no structured headers."""
    plain_analysis = "Some free-form analysis text with no headers at all."
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "ai_analysis": plain_analysis})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_works_with_very_long_ai_analysis() -> None:
    long_analysis = (
        "EXECUTIVE SUMMARY\nLong text. " + ("word " * 500) + "\n\n"
        "KEY FINDINGS\n* Finding one.\n* Finding two.\n\n"
        "IMPROVEMENT RECOMMENDATIONS\n1. Rec one.\n\n"
        "LONG-TERM OUTLOOK\nFuture looks bright."
    )
    resp = client.post("/api/v1/simulation/report", json={**_REPORT_BASE, "ai_analysis": long_analysis})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  /api/v1/ai/goal-to-actions — input validation (always runnable)
# ═══════════════════════════════════════════════════════════════════════════════

def test_goal_to_actions_rejects_unknown_zone() -> None:
    resp = client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": "Reduce pollution", "zone_id": "zone_does_not_exist"},
    )
    assert resp.status_code == 404


def test_goal_to_actions_rejects_goal_too_short() -> None:
    resp = client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": "Hi", "zone_id": ZONE_ID},
    )
    assert resp.status_code == 422


def test_goal_to_actions_rejects_goal_exactly_four_chars() -> None:
    resp = client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": "Abcd", "zone_id": ZONE_ID},
    )
    assert resp.status_code == 422


def test_goal_to_actions_rejects_goal_too_long() -> None:
    resp = client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": "A" * 501, "zone_id": ZONE_ID},
    )
    assert resp.status_code == 422


def test_goal_to_actions_rejects_missing_zone_id() -> None:
    resp = client.post("/api/v1/ai/goal-to-actions", json={"goal": "Reduce pollution in this area"})
    assert resp.status_code == 422


def test_goal_to_actions_rejects_missing_goal() -> None:
    resp = client.post("/api/v1/ai/goal-to-actions", json={"zone_id": ZONE_ID})
    assert resp.status_code == 422


@_SKIP_HAS_KEY
def test_goal_to_actions_returns_503_without_key() -> None:
    resp = client.post(
        "/api/v1/ai/goal-to-actions",
        json={"goal": "Reduce pollution in this city", "zone_id": ZONE_ID},
    )
    assert resp.status_code == 503


# ── Live tests using session fixture (1 Gemini call total) ───────────────────

@_LIVE
@_SKIP_NO_KEY
def test_goal_to_actions_response_has_goal_and_zone(gemini_actions: list[dict]) -> None:
    assert isinstance(gemini_actions, list)
    assert len(gemini_actions) >= 2


@_LIVE
@_SKIP_NO_KEY
def test_goal_to_actions_each_action_has_valid_fields(gemini_actions: list[dict]) -> None:
    for action in gemini_actions:
        assert isinstance(action["action_type"], str)
        assert len(action["action_type"]) > 0
        assert 0.0 < action["intensity"] <= 1.0
        assert 1 <= action["duration_years"] <= 10


@_LIVE
@_SKIP_NO_KEY
def test_goal_to_actions_returned_types_accepted_by_simulation(
    gemini_actions: list[dict],
    simulation_result: dict,
) -> None:
    """Gemini action types round-trip through the simulation engine without error."""
    assert simulation_result["sustainability_score"] >= 0
    assert len(simulation_result["projected_zones"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  /api/v1/ai/suggest-improvements — input validation (always runnable)
# ═══════════════════════════════════════════════════════════════════════════════

_SUGGEST_BASE = dict(
    goal="Reduce pollution but keep traffic flowing",
    zone_id=ZONE_ID,
    zone_name="Calumet Industrial Strip",
    actions=ACTIONS,
    initial_metrics=INITIAL_METRICS,
    final_metrics=FINAL_METRICS,
    projection_years=5,
    sustainability_score=33.0,
    overall_outlook="moderate",
)


def test_suggest_improvements_rejects_missing_goal() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "goal"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_zone_name() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "zone_name"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_zone_id() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "zone_id"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_actions() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "actions"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_initial_metrics() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "initial_metrics"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_final_metrics() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "final_metrics"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_sustainability_score() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "sustainability_score"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_missing_overall_outlook() -> None:
    payload = {k: v for k, v in _SUGGEST_BASE.items() if k != "overall_outlook"}
    assert client.post("/api/v1/ai/suggest-improvements", json=payload).status_code == 422


def test_suggest_improvements_rejects_invalid_projection_years() -> None:
    resp = client.post("/api/v1/ai/suggest-improvements",
                       json={**_SUGGEST_BASE, "projection_years": 0})
    assert resp.status_code == 422


def test_suggest_improvements_rejects_projection_years_above_max() -> None:
    resp = client.post("/api/v1/ai/suggest-improvements",
                       json={**_SUGGEST_BASE, "projection_years": 51})
    assert resp.status_code == 422


def test_suggest_improvements_rejects_projection_years_negative() -> None:
    resp = client.post("/api/v1/ai/suggest-improvements",
                       json={**_SUGGEST_BASE, "projection_years": -1})
    assert resp.status_code == 422


@_SKIP_HAS_KEY
def test_suggest_improvements_returns_503_without_key() -> None:
    assert client.post("/api/v1/ai/suggest-improvements", json=_SUGGEST_BASE).status_code == 503


# ── Live tests using session fixture (1 Gemini call total) ───────────────────

@_LIVE
@_SKIP_NO_KEY
def test_suggest_improvements_returns_non_empty_text(gemini_analysis: str) -> None:
    assert isinstance(gemini_analysis, str)
    assert len(gemini_analysis) > 200


@_LIVE
@_SKIP_NO_KEY
def test_suggest_improvements_contains_all_sections(gemini_analysis: str) -> None:
    upper = gemini_analysis.upper()
    assert "EXECUTIVE SUMMARY" in upper
    assert "KEY FINDINGS" in upper
    assert "IMPROVEMENT RECOMMENDATIONS" in upper
    assert "LONG-TERM OUTLOOK" in upper


@_LIVE
@_SKIP_NO_KEY
def test_suggest_improvements_references_zone_name(gemini_analysis: str) -> None:
    assert "Asia" in gemini_analysis


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  End-to-end: fixture results feed directly into the PDF report
# ═══════════════════════════════════════════════════════════════════════════════

@_LIVE
@_SKIP_NO_KEY
def test_e2e_pdf_from_fixture_pipeline(
    gemini_actions: list[dict],
    projected_zone: dict,
    simulation_result: dict,
    gemini_analysis: str,
) -> None:
    """Full pipeline: AI actions → simulation → analysis → PDF — no extra Gemini calls."""
    pdf_resp = client.post(
        "/api/v1/simulation/report",
        json={
            "goal": "Reduce pollution but keep traffic flowing",
            "zone_name": "Asia",
            "zone_type": "continent",
            "actions": gemini_actions,
            "initial_metrics": INITIAL_METRICS,
            "final_metrics": projected_zone,
            "projection_years": 5,
            "sustainability_score": simulation_result["sustainability_score"],
            "overall_outlook": simulation_result.get("overall_outlook", "mixed"),
            "ai_analysis": gemini_analysis,
        },
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"
    assert len(pdf_resp.content) > 2000
