from app.core.constants import RiskLevel
from app.models.domain.action import ActionType, SimulationAction
from app.models.domain.zone import ZoneState, ZoneType
from app.rules import deforestation, pollution, restoration, traffic
from app.services.impact_service import impact_service
from app.services.simulation_engine import simulation_engine


def make_zone() -> ZoneState:
    return ZoneState(
        zone_id="zone_test",
        name="Test Zone",
        type=ZoneType.FOREST,
        tree_cover=60,
        biodiversity_score=72,
        pollution_level=22,
        traffic_level=18,
        temperature=21.5,
        ecosystem_health=70,
        risk_level=RiskLevel.LOW,
    )


def test_deforestation_rule_reduces_nature_and_heats_zone() -> None:
    zone = make_zone()

    updated = deforestation.apply(zone, intensity=0.8, duration_years=2)

    assert updated.tree_cover < 60
    assert updated.biodiversity_score < 72
    assert updated.ecosystem_health < 70
    assert updated.temperature > 21.5
    assert 0 <= updated.tree_cover <= 100


def test_traffic_rule_increases_pressure_metrics() -> None:
    zone = make_zone()

    updated = traffic.apply(zone, intensity=0.7, duration_years=3)

    assert updated.traffic_level > 18
    assert updated.pollution_level > 22
    assert updated.temperature > 21.5
    assert updated.ecosystem_health < 70
    assert 0 <= updated.traffic_level <= 100


def test_pollution_rule_spikes_pollution_and_clamps_values() -> None:
    zone = make_zone()
    zone.pollution_level = 96

    updated = pollution.apply(zone, intensity=1.0, duration_years=2)

    assert updated.pollution_level == 100
    assert updated.biodiversity_score < 72
    assert updated.ecosystem_health < 70
    assert updated.tree_cover < 60


def test_restoration_rule_improves_recovery_metrics() -> None:
    zone = make_zone()
    zone.tree_cover = 95
    zone.biodiversity_score = 96
    zone.ecosystem_health = 97

    updated = restoration.apply(zone, intensity=1.0, duration_years=2)

    assert updated.tree_cover == 100
    assert updated.biodiversity_score == 100
    assert updated.ecosystem_health == 100
    assert updated.temperature < 21.5
    assert updated.pollution_level <= 22


def test_simulation_engine_recomputes_risk_after_action() -> None:
    zone = make_zone()
    action = SimulationAction(
        zone_id=zone.zone_id,
        action_type=ActionType.POLLUTION_SPIKE,
        intensity=1.0,
        duration_years=3,
    )

    updated_zone = simulation_engine.simulate_zone_action(zone, action)

    assert updated_zone.risk_level == impact_service.compute_risk_level(updated_zone)
    assert updated_zone.risk_level in {
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    }
