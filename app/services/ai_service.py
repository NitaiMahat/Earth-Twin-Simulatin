from __future__ import annotations

from app.core.config import settings
from app.models.api.responses import AIExplainResponse
from app.models.domain.action import AudienceType, SimulationMode
from app.models.domain.zone import ZoneState
from app.repositories.zone_repository import zone_repository
from app.services.impact_service import impact_service


class AIService:
    def explain(
        self,
        zone_id: str,
        context: str,
        question: str,
        mode: SimulationMode,
        audience: AudienceType,
        location_label: str | None = None,
    ) -> AIExplainResponse:
        zone = zone_repository.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Zone '{zone_id}' was not found.")

        zone = impact_service.normalize_zone(zone)
        if location_label:
            zone = zone.model_copy(update={"name": location_label})
        cleaned_context = context.strip()
        tone = self._resolve_tone(mode, audience)

        answer = self._build_answer(zone, cleaned_context, question, mode, audience)
        bullets = self._build_bullets(zone, cleaned_context, mode, audience)
        recommended_actions = self._build_recommendations(zone, mode, audience)

        return AIExplainResponse(
            answer=answer,
            bullets=bullets,
            recommended_actions=recommended_actions,
            tone=tone,
            audience=audience,
            mode=mode,
        )

    def _resolve_tone(self, mode: SimulationMode, audience: AudienceType) -> str:
        if audience in {AudienceType.PLANNER, AudienceType.MUNICIPALITY} or mode == SimulationMode.PLANNING:
            return "decision-support"
        if audience in {AudienceType.STUDENT, AudienceType.EDUCATOR} or mode == SimulationMode.LEARNING:
            return "educational"
        return "plain-language"

    def _build_answer(
        self,
        zone: ZoneState,
        context: str,
        question: str,
        mode: SimulationMode,
        audience: AudienceType,
    ) -> str:
        if settings.llm_explanations_enabled:
            return self._build_llm_ready_answer(zone, context, question, mode, audience)
        return self._build_deterministic_answer(zone, context, question, mode, audience)

    def _build_deterministic_answer(
        self,
        zone: ZoneState,
        context: str,
        question: str,
        mode: SimulationMode,
        audience: AudienceType,
    ) -> str:
        top_drivers = impact_service.get_top_driver_names(zone, limit=2)
        driver_phrase = " and ".join(top_drivers)
        context_note = self._build_context_note(context)
        recommended_focus = impact_service.build_zone_recommended_focus(zone)

        if mode == SimulationMode.LEARNING or audience in {AudienceType.STUDENT, AudienceType.EDUCATOR}:
            return (
                f"For {zone.name}, the answer to '{question}' is that the zone is at "
                f"{zone.risk_level.value} risk with a sustainability score of {zone.sustainability_score}. "
                f"The biggest drivers are {driver_phrase}. This means the ecosystem is under stress and "
                f"shows how land use, heat, and pollution interact over time. {recommended_focus}{context_note}"
            )

        return (
            f"For {zone.name}, the answer to '{question}' is that the zone is at "
            f"{zone.risk_level.value} risk with a sustainability score of {zone.sustainability_score}. "
            f"The main decision drivers are {driver_phrase}. {recommended_focus}{context_note}"
        )

    def _build_llm_ready_answer(
        self,
        zone: ZoneState,
        context: str,
        question: str,
        mode: SimulationMode,
        audience: AudienceType,
    ) -> str:
        # Placeholder for a future real LLM client. The deterministic branch remains
        # the default so the backend is usable without external credentials.
        return self._build_deterministic_answer(zone, context, question, mode, audience)

    def _build_context_note(self, context: str) -> str:
        if not context:
            return ""
        normalized_context = context.strip().rstrip(".!? ")
        return f" Scenario context: {normalized_context}."

    def _build_bullets(
        self,
        zone: ZoneState,
        context: str,
        mode: SimulationMode,
        audience: AudienceType,
    ) -> list[str]:
        if mode == SimulationMode.LEARNING or audience in {AudienceType.STUDENT, AudienceType.EDUCATOR}:
            bullets = [
                (
                    f"{zone.name} is at {zone.risk_level.value} risk and has a sustainability score of "
                    f"{zone.sustainability_score}."
                ),
                (
                    f"When tree cover is {zone.tree_cover} and biodiversity is {zone.biodiversity_score}, "
                    "the ecosystem has less capacity to recover."
                ),
                (
                    f"Pollution at {zone.pollution_level} and temperature at {zone.temperature} show how "
                    "environmental stress can build over time."
                ),
                (
                    f"Ecosystem health at {zone.ecosystem_health} helps explain why the zone is more or less resilient."
                ),
            ]
            if context:
                bullets.append(
                    f"Scenario context used for this explanation: {context.strip().rstrip('.!? ')}."
                )
            return bullets[:5]

        bullets = [
            (
                f"Risk level is {zone.risk_level.value} and sustainability score is {zone.sustainability_score}."
            ),
            (
                f"Top drivers are {', '.join(impact_service.get_top_driver_names(zone, limit=3))}."
            ),
            impact_service.build_zone_recommended_focus(zone),
        ]
        if zone.pollution_level > 50 or zone.temperature > 26:
            bullets.append(
                f"Pollution ({zone.pollution_level}) and temperature ({zone.temperature}) indicate continued stress if no mitigation is added."
            )
        if context:
            bullets.append(
                f"Scenario context used for this explanation: {context.strip().rstrip('.!? ')}."
            )
        return bullets[:5]

    def _build_recommendations(
        self,
        zone: ZoneState,
        mode: SimulationMode,
        audience: AudienceType,
    ) -> list[str]:
        base_recommendations: list[str] = []

        if zone.tree_cover < 40:
            base_recommendations.append("Restore tree cover and reconnect habitat where possible.")
        if zone.traffic_level > 60:
            base_recommendations.append("Reduce transport pressure or shift trips to lower-impact mobility options.")
        if zone.pollution_level > 50:
            base_recommendations.append("Cut local emissions and address pollution hotspots first.")
        if zone.ecosystem_health < 50:
            base_recommendations.append("Stabilize ecosystem health before adding new development pressure.")
        if zone.temperature > 26:
            base_recommendations.append("Add cooling, shade, and green infrastructure to reduce heat stress.")
        if zone.biodiversity_score < 50:
            base_recommendations.append("Protect vulnerable habitats and support species recovery.")

        if not base_recommendations:
            base_recommendations = [
                "Maintain current protections and keep monitoring for early warning changes.",
                "Use light restoration and pollution control to preserve the current gains.",
            ]

        if mode == SimulationMode.LEARNING or audience in {AudienceType.STUDENT, AudienceType.EDUCATOR}:
            return [f"Try this next: {recommendation}" for recommendation in base_recommendations[:4]]

        return base_recommendations[:4]


ai_service = AIService()
