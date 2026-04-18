from __future__ import annotations

from app.core.constants import (
    PASSIVE_WARMING_PER_YEAR,
    RISK_ORDER,
    RiskLevel,
    SUSTAINABILITY_RISK_PENALTY,
    WORLD_CO2_BASE,
    WORLD_TEMPERATURE_BASE,
    ZONE_TEMPERATURE_MAX,
    ZONE_TEMPERATURE_MIN,
    ZONE_VALUE_MAX,
    ZONE_VALUE_MIN,
)
from app.models.domain.action import SimulationMode
from app.models.domain.simulation import CompactZoneSummary, DerivedEffects, ProjectionMetrics
from app.models.domain.world import WorldState
from app.models.domain.zone import ZoneState


class ImpactService:
    def clamp(self, value: float, minimum: float, maximum: float) -> float:
        return round(max(minimum, min(maximum, value)), 2)

    def normalize_zone(self, zone: ZoneState) -> ZoneState:
        zone.tree_cover = self.clamp(zone.tree_cover, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
        zone.biodiversity_score = self.clamp(
            zone.biodiversity_score,
            ZONE_VALUE_MIN,
            ZONE_VALUE_MAX,
        )
        zone.pollution_level = self.clamp(zone.pollution_level, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
        zone.traffic_level = self.clamp(zone.traffic_level, ZONE_VALUE_MIN, ZONE_VALUE_MAX)
        zone.temperature = self.clamp(zone.temperature, ZONE_TEMPERATURE_MIN, ZONE_TEMPERATURE_MAX)
        zone.ecosystem_health = self.clamp(
            zone.ecosystem_health,
            ZONE_VALUE_MIN,
            ZONE_VALUE_MAX,
        )
        zone.risk_level = self.compute_risk_level(zone)
        zone.sustainability_score = self.compute_sustainability_score(zone)
        return zone

    def get_risk_components(self, zone: ZoneState) -> dict[str, float]:
        return {
            "high pollution": round(zone.pollution_level * 0.3, 2),
            "high traffic": round(zone.traffic_level * 0.1, 2),
            "low tree cover": round((100.0 - zone.tree_cover) * 0.2, 2),
            "low biodiversity": round((100.0 - zone.biodiversity_score) * 0.25, 2),
            "low ecosystem health": round((100.0 - zone.ecosystem_health) * 0.35, 2),
            "high temperature": round(max(0.0, zone.temperature - 20.0) * 2.0, 2),
        }

    def compute_risk_score(self, zone: ZoneState) -> float:
        return round(sum(self.get_risk_components(zone).values()), 2)

    def compute_risk_level(self, zone: ZoneState) -> RiskLevel:
        risk_score = self.compute_risk_score(zone)

        if risk_score < 45:
            return RiskLevel.LOW
        if risk_score < 70:
            return RiskLevel.MEDIUM
        if risk_score < 95:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    def compute_sustainability_score(self, zone: ZoneState) -> float:
        temperature_score = self.clamp(100.0 - (abs(zone.temperature - 22.0) * 4.0), 0.0, 100.0)
        base_score = (
            (zone.tree_cover * 0.22)
            + (zone.biodiversity_score * 0.22)
            + (zone.ecosystem_health * 0.24)
            + ((100.0 - zone.pollution_level) * 0.16)
            + ((100.0 - zone.traffic_level) * 0.08)
            + (temperature_score * 0.08)
        )
        penalty = SUSTAINABILITY_RISK_PENALTY[zone.risk_level]
        return self.clamp(base_score - penalty, 0.0, 100.0)

    def compute_world_sustainability_score(self, world: WorldState) -> float:
        if not world.zones:
            return 0.0
        average_score = sum(zone.sustainability_score for zone in world.zones) / len(world.zones)
        return self.clamp(average_score, 0.0, 100.0)

    def get_top_driver_names(self, zone: ZoneState, limit: int = 3) -> list[str]:
        ranked_components = sorted(
            self.get_risk_components(zone).items(),
            key=lambda item: item[1],
            reverse=True,
        )
        top_drivers = [name for name, score in ranked_components if score > 0][:limit]
        return top_drivers or ["stable conditions"]

    def build_top_drivers(self, zone: ZoneState, limit: int = 3) -> list[str]:
        top_driver_names = self.get_top_driver_names(zone, limit=limit)
        if top_driver_names == ["stable conditions"]:
            return ["Current conditions are relatively stable across the tracked risk factors."]

        messages: list[str] = []
        for driver_name in top_driver_names:
            if driver_name == "high pollution":
                messages.append(
                    f"High pollution ({zone.pollution_level}) is adding direct environmental stress."
                )
            elif driver_name == "high traffic":
                messages.append(f"High traffic ({zone.traffic_level}) is increasing ongoing pressure.")
            elif driver_name == "low tree cover":
                messages.append(f"Low tree cover ({zone.tree_cover}) limits natural cooling and recovery.")
            elif driver_name == "low biodiversity":
                messages.append(
                    f"Low biodiversity ({zone.biodiversity_score}) weakens ecosystem resilience."
                )
            elif driver_name == "low ecosystem health":
                messages.append(
                    f"Low ecosystem health ({zone.ecosystem_health}) reduces the zone's ability to absorb shocks."
                )
            elif driver_name == "high temperature":
                messages.append(f"High temperature ({zone.temperature}) is amplifying heat stress.")
        return messages

    def build_risk_summary(self, zone: ZoneState) -> str:
        risk_score = self.compute_risk_score(zone)
        risk_level = self.compute_risk_level(zone)
        top_driver_names = self.get_top_driver_names(zone, limit=2)
        leading_drivers = ", ".join(top_driver_names)
        return (
            f"{zone.name} is currently {risk_level.value} risk with a deterministic score of {risk_score}. "
            f"Main drivers: {leading_drivers}."
        )

    def build_zone_recommended_focus(self, zone: ZoneState) -> str:
        top_driver_names = self.get_top_driver_names(zone, limit=2)

        if "high pollution" in top_driver_names and "high traffic" in top_driver_names:
            return f"Prioritize emissions reduction and transport pressure relief in {zone.name}."
        if "low tree cover" in top_driver_names or "low biodiversity" in top_driver_names:
            return f"Prioritize green restoration and habitat recovery in {zone.name}."
        if "low ecosystem health" in top_driver_names:
            return f"Stabilize ecosystem health in {zone.name} before adding new development pressure."
        if "high temperature" in top_driver_names:
            return f"Focus on cooling strategies and heat mitigation in {zone.name}."
        return f"Maintain protections in {zone.name} and monitor for early warning changes."

    def build_projection_recommended_focus(
        self,
        projected_world: WorldState,
        highest_risk_zone: ZoneState | None,
    ) -> str:
        if highest_risk_zone is None:
            return "Monitor the overall system and maintain the current sustainability gains."
        zone_focus = self.build_zone_recommended_focus(highest_risk_zone)
        return f"{zone_focus} This zone is the main leverage point for improving the overall projection."

    def build_metric_delta_messages(
        self,
        before_state: ZoneState,
        after_state: ZoneState,
        limit: int = 4,
    ) -> list[str]:
        delta = self.build_derived_effects(before_state, after_state)
        metric_changes = [
            ("tree_cover", delta.tree_cover_delta),
            ("biodiversity_score", delta.biodiversity_delta),
            ("pollution_level", delta.pollution_delta),
            ("traffic_level", delta.traffic_delta),
            ("temperature", delta.temperature_delta),
            ("ecosystem_health", delta.ecosystem_health_delta),
        ]
        metric_changes.sort(key=lambda item: abs(item[1]), reverse=True)

        messages: list[str] = []
        for metric_name, value in metric_changes:
            if value == 0:
                continue
            direction = "increased" if value > 0 else "decreased"
            abs_value = round(abs(value), 2)
            if metric_name == "tree_cover":
                messages.append(
                    f"Tree cover {direction} by {abs_value} points, affecting shade and habitat stability."
                )
            elif metric_name == "biodiversity_score":
                messages.append(
                    f"Biodiversity {direction} by {abs_value} points, changing ecosystem resilience."
                )
            elif metric_name == "pollution_level":
                messages.append(
                    f"Pollution {direction} by {abs_value} points, changing environmental stress."
                )
            elif metric_name == "traffic_level":
                messages.append(
                    f"Traffic pressure {direction} by {abs_value} points, influencing congestion and emissions."
                )
            elif metric_name == "temperature":
                messages.append(
                    f"Temperature {direction} by {abs_value} C, changing local heat stress."
                )
            elif metric_name == "ecosystem_health":
                messages.append(
                    f"Ecosystem health {direction} by {abs_value} points, shifting the zone's recovery capacity."
                )
            if len(messages) >= limit:
                break

        return messages or ["No significant environmental shift was detected in the tracked metrics."]

    def build_apply_summary(
        self,
        zone: ZoneState,
        requested_action_type: str,
        normalized_action_type: str,
        mode: SimulationMode,
    ) -> str:
        focus = self.build_zone_recommended_focus(zone)
        requested_label = requested_action_type.replace("_", " ")
        normalized_label = normalized_action_type.replace("_", " ")

        if mode == SimulationMode.LEARNING:
            return (
                f"In learning mode, {requested_label} maps to {normalized_label}. "
                f"{zone.name} is now {zone.risk_level.value} risk with a sustainability score of "
                f"{zone.sustainability_score}. This shows how land use, heat, and ecosystem pressure combine. "
                f"{focus}"
            )

        return (
            f"In planning mode, {requested_label} maps to {normalized_label}. "
            f"{zone.name} is now {zone.risk_level.value} risk with a sustainability score of "
            f"{zone.sustainability_score}. {focus}"
        )

    def refresh_world(self, world: WorldState) -> WorldState:
        for zone in world.zones:
            self.normalize_zone(zone)

        if not world.zones:
            world.global_temperature = WORLD_TEMPERATURE_BASE
            world.global_co2_index = WORLD_CO2_BASE
            world.sustainability_score = 0.0
            return world

        average_zone_temp = sum(zone.temperature for zone in world.zones) / len(world.zones)
        average_pollution = sum(zone.pollution_level for zone in world.zones) / len(world.zones)
        average_traffic = sum(zone.traffic_level for zone in world.zones) / len(world.zones)
        average_tree_cover = sum(zone.tree_cover for zone in world.zones) / len(world.zones)

        world.global_temperature = round(
            WORLD_TEMPERATURE_BASE + (average_zone_temp * 0.06) + (average_pollution * 0.015),
            2,
        )
        world.global_co2_index = round(
            WORLD_CO2_BASE
            + (average_pollution * 0.9)
            + (average_traffic * 0.4)
            - (average_tree_cover * 0.15),
            2,
        )
        world.sustainability_score = self.compute_world_sustainability_score(world)
        return world

    def build_derived_effects(self, before_state: ZoneState, after_state: ZoneState) -> DerivedEffects:
        return DerivedEffects(
            tree_cover_delta=round(after_state.tree_cover - before_state.tree_cover, 2),
            biodiversity_delta=round(after_state.biodiversity_score - before_state.biodiversity_score, 2),
            pollution_delta=round(after_state.pollution_level - before_state.pollution_level, 2),
            traffic_delta=round(after_state.traffic_level - before_state.traffic_level, 2),
            temperature_delta=round(after_state.temperature - before_state.temperature, 2),
            ecosystem_health_delta=round(after_state.ecosystem_health - before_state.ecosystem_health, 2),
        )

    def get_highest_risk_zone(self, zones: list[ZoneState]) -> ZoneState | None:
        if not zones:
            return None

        return max(
            zones,
            key=lambda zone: (
                RISK_ORDER[zone.risk_level],
                zone.pollution_level,
                zone.temperature,
                -zone.ecosystem_health,
            ),
        )

    def build_projection_metrics(
        self,
        base_world: WorldState,
        projected_world: WorldState,
    ) -> ProjectionMetrics:
        base_by_id = {zone.zone_id: zone for zone in base_world.zones}
        biodiversity_drops: list[float] = []
        temperature_changes: list[float] = []

        for projected_zone in projected_world.zones:
            base_zone = base_by_id.get(projected_zone.zone_id)
            if base_zone is None:
                continue
            biodiversity_drops.append(base_zone.biodiversity_score - projected_zone.biodiversity_score)
            temperature_changes.append(projected_zone.temperature - base_zone.temperature)

        average_biodiversity_drop = 0.0
        average_temperature_change = 0.0
        if biodiversity_drops:
            average_biodiversity_drop = round(sum(biodiversity_drops) / len(biodiversity_drops), 2)
        if temperature_changes:
            average_temperature_change = round(sum(temperature_changes) / len(temperature_changes), 2)

        return ProjectionMetrics(
            highest_risk_zone=self.get_highest_risk_zone(projected_world.zones),
            average_biodiversity_drop=average_biodiversity_drop,
            average_temperature_change=average_temperature_change,
        )

    def build_projection_summary(
        self,
        projected_world: WorldState,
        metrics: ProjectionMetrics,
        mode: SimulationMode = SimulationMode.PLANNING,
    ) -> str:
        highest_risk_zone = metrics.highest_risk_zone.name if metrics.highest_risk_zone else "no zone"
        if mode == SimulationMode.LEARNING:
            return (
                f"By {projected_world.current_year}, the simulation shows how the selected actions change heat, "
                f"pollution, and biodiversity over time. {highest_risk_zone} becomes the most stressed zone. "
                f"Average biodiversity change is {metrics.average_biodiversity_drop} points and average "
                f"temperature change is {metrics.average_temperature_change} C."
            )

        return (
            f"Projected to {projected_world.current_year}. Highest risk is {highest_risk_zone}. "
            f"Average biodiversity drop is {metrics.average_biodiversity_drop} points and average "
            f"temperature change is {metrics.average_temperature_change} C."
        )

    def build_projection_headline(
        self,
        projected_world: WorldState,
        mode: SimulationMode,
        overall_outlook: str,
    ) -> str:
        if mode == SimulationMode.LEARNING:
            return f"Learning outlook for {projected_world.name}: {overall_outlook.title()}"
        return f"Planning outlook for {projected_world.name}: {overall_outlook.title()}"

    def build_overall_outlook(self, world: WorldState) -> str:
        has_critical_zone = any(zone.risk_level == RiskLevel.CRITICAL for zone in world.zones)
        has_high_zone = any(zone.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} for zone in world.zones)

        if world.sustainability_score < 45 or has_critical_zone:
            return "negative"
        if 45 <= world.sustainability_score <= 69 or has_high_zone:
            return "mixed"
        return "positive"

    def build_compact_zone_summary(self, zone: ZoneState | None) -> CompactZoneSummary | None:
        if zone is None:
            return None
        return CompactZoneSummary(
            zone_id=zone.zone_id,
            name=zone.name,
            risk_level=zone.risk_level,
            sustainability_score=zone.sustainability_score,
        )

    def build_comparison_tradeoffs(
        self,
        scenario_names: list[str],
        recommended_scenario: str | None,
        scenario_metrics: dict[str, dict[str, float]],
    ) -> list[str]:
        if len(scenario_names) < 2:
            return ["Only one scenario was available, so no tradeoff analysis was needed."]

        top_name = recommended_scenario or scenario_names[0]
        worst_name = min(
            scenario_names,
            key=lambda name: (
                scenario_metrics[name]["sustainability_score"],
                scenario_metrics[name]["avg_temperature_change"],
                scenario_metrics[name]["avg_biodiversity_drop"],
            ),
        )
        if top_name == worst_name and len(scenario_names) > 1:
            worst_name = next(name for name in scenario_names if name != top_name)

        top_metrics = scenario_metrics[top_name]
        worst_metrics = scenario_metrics[worst_name]
        tradeoffs = [
            (
                f"{top_name} keeps sustainability at {top_metrics['sustainability_score']} compared with "
                f"{worst_name} at {worst_metrics['sustainability_score']}."
            ),
            (
                f"{top_name} changes temperature by {top_metrics['avg_temperature_change']} C versus "
                f"{worst_name} at {worst_metrics['avg_temperature_change']} C."
            ),
            (
                f"{top_name} changes biodiversity by {top_metrics['avg_biodiversity_drop']} points versus "
                f"{worst_name} at {worst_metrics['avg_biodiversity_drop']}."
            ),
        ]
        return tradeoffs[:3]

    def build_comparison_summary(
        self,
        recommended_scenario: str | None,
        mode: SimulationMode,
    ) -> str:
        if recommended_scenario is None:
            return "No scenario comparison result was available."
        if mode == SimulationMode.LEARNING:
            return (
                f"{recommended_scenario} is the strongest learning outcome because it keeps more of the system "
                f"stable while showing clearer sustainability gains."
            )
        return (
            f"{recommended_scenario} is the preferred scenario because it delivers the strongest sustainability "
            f"outcome with lower long-term environmental risk."
        )

    def apply_passive_drift(self, zone: ZoneState) -> ZoneState:
        zone.temperature += PASSIVE_WARMING_PER_YEAR + (zone.pollution_level * 0.001)
        zone.tree_cover += 0.15 - (zone.pollution_level * 0.005) - (zone.traffic_level * 0.002)
        zone.pollution_level += (zone.traffic_level * 0.01) - (zone.tree_cover * 0.008)
        zone.biodiversity_score += (
            (zone.tree_cover * 0.01) - (zone.pollution_level * 0.012) - (zone.traffic_level * 0.004)
        )
        zone.ecosystem_health += (
            (zone.biodiversity_score * 0.008)
            + (zone.tree_cover * 0.004)
            - (zone.pollution_level * 0.012)
            - (zone.traffic_level * 0.004)
        )
        return self.normalize_zone(zone)


impact_service = ImpactService()
