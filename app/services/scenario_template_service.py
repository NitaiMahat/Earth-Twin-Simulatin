from __future__ import annotations

import json

from app.core.config import settings
from app.models.domain.action import SimulationAction, SimulationMode
from app.models.domain.scenario_template import ScenarioTemplate
from app.models.domain.simulation import ProjectionSimulationResult
from app.services.action_mapper import action_mapper
from app.services.simulation_engine import simulation_engine
from app.services.world_service import world_service


class ScenarioTemplateService:
    def __init__(self) -> None:
        self._templates = self._load_templates()

    def _load_templates(self) -> list[ScenarioTemplate]:
        with settings.scenario_templates_path.open("r", encoding="utf-8") as template_file:
            payload = json.load(template_file)
        return [ScenarioTemplate.model_validate(item) for item in payload]

    def list_templates(self, mode: SimulationMode | None = None) -> list[ScenarioTemplate]:
        if mode is None:
            return self._templates
        return [template for template in self._templates if template.mode == mode]

    def get_template(self, template_id: str) -> ScenarioTemplate:
        for template in self._templates:
            if template.template_id == template_id:
                return template
        raise ValueError(f"Scenario template '{template_id}' was not found.")

    def _build_simulation_actions(self, template: ScenarioTemplate) -> list[SimulationAction]:
        return [
            SimulationAction(
                zone_id=action.zone_id,
                action_type=action_mapper.normalize_action_type(action.action_type),
                intensity=action.intensity,
                duration_years=action.duration_years,
            )
            for action in template.default_actions
        ]

    def run_template(
        self,
        template_id: str,
        base_world_id: str | None = None,
        projection_years: int | None = None,
        mode: SimulationMode | None = None,
    ) -> tuple[ScenarioTemplate, ProjectionSimulationResult]:
        template = self.get_template(template_id)
        world = world_service.get_world()
        resolved_world_id = base_world_id or world.world_id
        resolved_projection_years = projection_years or template.default_projection_years
        resolved_mode = mode or template.mode
        actions = self._build_simulation_actions(template)

        projection = simulation_engine.project_world_result(
            base_world_id=resolved_world_id,
            actions=actions,
            projection_years=resolved_projection_years,
            mode=resolved_mode,
        )
        return template, projection


scenario_template_service = ScenarioTemplateService()
