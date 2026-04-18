from __future__ import annotations

from app.core.constants import RISK_ORDER
from app.models.domain.action import ActionType, SimulationAction, SimulationMode
from app.models.domain.simulation import (
    ActionSimulationResult,
    ComparedScenarioResult,
    ComparisonSimulationResult,
    ProjectionMetrics,
    ProjectionSimulationResult,
)
from app.models.domain.world import WorldState
from app.models.domain.zone import ZoneState
from app.repositories.world_repository import world_repository
from app.rules import deforestation, pollution, restoration, traffic
from app.services.impact_service import impact_service


RULES_BY_ACTION = {
    ActionType.DEFORESTATION: deforestation.apply,
    ActionType.TRAFFIC_INCREASE: traffic.apply,
    ActionType.POLLUTION_SPIKE: pollution.apply,
    ActionType.RESTORATION: restoration.apply,
}


class SimulationEngine:
    def _get_zone_from_world(self, world: WorldState, zone_id: str) -> ZoneState:
        for zone in world.zones:
            if zone.zone_id == zone_id:
                return zone
        raise ValueError(f"Zone '{zone_id}' was not found.")

    def simulate_zone_action(self, zone: ZoneState, action: SimulationAction) -> ZoneState:
        rule = RULES_BY_ACTION[action.action_type]
        updated_zone = rule(zone, action.intensity, action.duration_years)
        return impact_service.normalize_zone(updated_zone)

    def apply_action(self, action: SimulationAction) -> ActionSimulationResult:
        world = world_repository.get_world()
        zone = self._get_zone_from_world(world, action.zone_id)
        before_state = zone.model_copy(deep=True)

        updated_zone = self.simulate_zone_action(zone, action)
        impact_service.refresh_world(world)
        world_repository.save_world(world)

        after_state = updated_zone.model_copy(deep=True)
        derived_effects = impact_service.build_derived_effects(before_state, after_state)

        return ActionSimulationResult(
            zone_id=zone.zone_id,
            action_type=action.action_type,
            before_state=before_state,
            after_state=after_state,
            derived_effects=derived_effects,
            risk_level=after_state.risk_level,
        )

    def _simulate_projection(
        self,
        base_world_id: str,
        actions: list[SimulationAction],
        projection_years: int,
        base_world_override: WorldState | None = None,
    ) -> tuple[WorldState, WorldState, ProjectionMetrics]:
        base_world = base_world_override.model_copy(deep=True) if base_world_override is not None else world_repository.get_world()
        impact_service.refresh_world(base_world)

        if base_world.world_id != base_world_id:
            raise ValueError(f"World '{base_world_id}' was not found.")

        projected_world = base_world.model_copy(deep=True)
        projected_world.current_year = base_world.current_year + projection_years

        for action in actions:
            target_zone = self._get_zone_from_world(projected_world, action.zone_id)
            effective_duration = min(action.duration_years, projection_years)
            effective_action = SimulationAction(
                zone_id=action.zone_id,
                action_type=action.action_type,
                intensity=action.intensity,
                duration_years=effective_duration,
            )
            self.simulate_zone_action(target_zone, effective_action)

        for _ in range(projection_years):
            for zone in projected_world.zones:
                impact_service.apply_passive_drift(zone)

        impact_service.refresh_world(projected_world)
        metrics = impact_service.build_projection_metrics(base_world, projected_world)
        return base_world, projected_world, metrics

    def project_world(
        self,
        base_world_id: str,
        actions: list[SimulationAction],
        projection_years: int,
        base_world_override: WorldState | None = None,
    ) -> tuple[WorldState, str, ZoneState | None, float, float]:
        _, projected_world, metrics = self._simulate_projection(
            base_world_id,
            actions,
            projection_years,
            base_world_override=base_world_override,
        )
        summary = impact_service.build_projection_summary(projected_world, metrics)

        return (
            projected_world,
            summary,
            metrics.highest_risk_zone,
            metrics.average_biodiversity_drop,
            metrics.average_temperature_change,
        )

    def project_world_result(
        self,
        base_world_id: str,
        actions: list[SimulationAction],
        projection_years: int,
        mode: SimulationMode,
        base_world_override: WorldState | None = None,
    ) -> ProjectionSimulationResult:
        _, projected_world, metrics = self._simulate_projection(
            base_world_id,
            actions,
            projection_years,
            base_world_override=base_world_override,
        )
        overall_outlook = impact_service.build_overall_outlook(projected_world)
        summary = impact_service.build_projection_headline(projected_world, mode, overall_outlook)
        summary_text = impact_service.build_projection_summary(projected_world, metrics, mode)
        highest_risk_zone_top_drivers = (
            impact_service.build_top_drivers(metrics.highest_risk_zone)
            if metrics.highest_risk_zone is not None
            else []
        )

        return ProjectionSimulationResult(
            projected_world=projected_world,
            mode=mode,
            summary=summary,
            summary_text=summary_text,
            highest_risk_zone=metrics.highest_risk_zone,
            highest_risk_zone_top_drivers=highest_risk_zone_top_drivers,
            avg_biodiversity_drop=metrics.average_biodiversity_drop,
            avg_temperature_change=metrics.average_temperature_change,
            sustainability_score=projected_world.sustainability_score,
            overall_outlook=overall_outlook,
            recommended_focus=impact_service.build_projection_recommended_focus(
                projected_world,
                metrics.highest_risk_zone,
            ),
        )

    def select_recommended_scenario(self, scenarios: list[ComparedScenarioResult]) -> str | None:
        if not scenarios:
            return None

        ranked_scenarios = sorted(
            scenarios,
            key=lambda scenario: (
                -scenario.sustainability_score,
                (
                    RISK_ORDER[scenario.highest_risk_zone.risk_level]
                    if scenario.highest_risk_zone is not None
                    else -1
                ),
                scenario.avg_temperature_change,
                scenario.avg_biodiversity_drop,
            ),
        )
        return ranked_scenarios[0].name

    def compare_scenarios(
        self,
        base_world_id: str,
        projection_years: int,
        mode: SimulationMode,
        scenarios: list[tuple[str, list[SimulationAction]]],
        base_world_override: WorldState | None = None,
    ) -> ComparisonSimulationResult:
        compared_scenarios: list[ComparedScenarioResult] = []

        for scenario_name, actions in scenarios:
            projection = self.project_world_result(
                base_world_id=base_world_id,
                actions=actions,
                projection_years=projection_years,
                mode=mode,
                base_world_override=base_world_override,
            )
            compared_scenarios.append(
                ComparedScenarioResult(
                    name=scenario_name,
                    summary=projection.summary,
                    summary_text=projection.summary_text,
                    highest_risk_zone=impact_service.build_compact_zone_summary(projection.highest_risk_zone),
                    avg_biodiversity_drop=projection.avg_biodiversity_drop,
                    avg_temperature_change=projection.avg_temperature_change,
                    sustainability_score=projection.sustainability_score,
                    overall_outlook=projection.overall_outlook,
                    recommended_focus=projection.recommended_focus,
                )
            )

        recommended_scenario = self.select_recommended_scenario(compared_scenarios)
        scenario_metrics = {
            scenario.name: {
                "sustainability_score": scenario.sustainability_score,
                "avg_temperature_change": scenario.avg_temperature_change,
                "avg_biodiversity_drop": scenario.avg_biodiversity_drop,
            }
            for scenario in compared_scenarios
        }

        return ComparisonSimulationResult(
            mode=mode,
            projection_years=projection_years,
            scenarios=compared_scenarios,
            recommended_scenario=recommended_scenario,
            key_tradeoffs=impact_service.build_comparison_tradeoffs(
                [scenario.name for scenario in compared_scenarios],
                recommended_scenario,
                scenario_metrics,
            ),
            comparison_summary_text=impact_service.build_comparison_summary(
                recommended_scenario,
                mode,
            ),
        )


simulation_engine = SimulationEngine()
