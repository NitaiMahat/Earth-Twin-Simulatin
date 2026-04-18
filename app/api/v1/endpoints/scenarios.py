from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, status

from app.models.api.requests import ScenarioTemplateRunRequest
from app.models.api.responses import (
    ScenarioTemplateDetailResponse,
    ScenarioTemplateListResponse,
    ScenarioTemplateResponse,
    ScenarioTemplateRunResponse,
)
from app.models.domain.action import SimulationMode
from app.services.scenario_template_service import scenario_template_service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("/templates", response_model=ScenarioTemplateListResponse)
def list_templates(mode: SimulationMode | None = None) -> ScenarioTemplateListResponse:
    templates = scenario_template_service.list_templates(mode=mode)
    response_templates = [ScenarioTemplateResponse.model_validate(template.model_dump()) for template in templates]
    return ScenarioTemplateListResponse(templates=response_templates, count=len(response_templates))


@router.get("/templates/{template_id}", response_model=ScenarioTemplateDetailResponse)
def get_template(template_id: str) -> ScenarioTemplateDetailResponse:
    try:
        template = scenario_template_service.get_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ScenarioTemplateDetailResponse(
        template=ScenarioTemplateResponse.model_validate(template.model_dump())
    )


@router.post("/templates/{template_id}/run", response_model=ScenarioTemplateRunResponse)
def run_template(
    template_id: str,
    payload: ScenarioTemplateRunRequest | None = Body(default=None),
) -> ScenarioTemplateRunResponse:
    overrides = payload or ScenarioTemplateRunRequest()
    resolved_projection_years = overrides.projection_years

    try:
        template, projection = scenario_template_service.run_template(
            template_id=template_id,
            base_world_id=overrides.base_world_id,
            projection_years=overrides.projection_years,
            mode=overrides.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ScenarioTemplateRunResponse(
        template_id=template.template_id,
        template_name=template.name,
        objective=template.objective,
        product_focus=template.product_focus,
        projection_years=resolved_projection_years or template.default_projection_years,
        mode=projection.mode,
        summary=projection.summary,
        summary_text=projection.summary_text,
        projected_zones=projection.projected_world.zones,
        highest_risk_zone=projection.highest_risk_zone,
        highest_risk_zone_top_drivers=projection.highest_risk_zone_top_drivers,
        avg_biodiversity_drop=projection.avg_biodiversity_drop,
        avg_temperature_change=projection.avg_temperature_change,
        sustainability_score=projection.sustainability_score,
        overall_outlook=projection.overall_outlook,
        recommended_focus=projection.recommended_focus,
    )
