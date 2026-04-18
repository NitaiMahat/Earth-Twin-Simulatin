from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import AIExplainRequest, ProjectFutureRequest, ScenarioTemplateRunRequest
from app.models.api.responses import (
    AIExplainResponse,
    ProjectFutureResponse,
    ScenarioTemplateDetailResponse,
    ScenarioTemplateListResponse,
    ScenarioTemplateResponse,
    ScenarioTemplateRunResponse,
)
from app.models.domain.action import AudienceType, SimulationAction, SimulationMode
from app.services.action_mapper import action_mapper
from app.services.ai_service import ai_service
from app.services.scenario_template_service import scenario_template_service
from app.services.simulation_engine import simulation_engine
from app.services.world_service import world_service

router = APIRouter(prefix="/education", tags=["education"])


@router.get("/scenarios/templates", response_model=ScenarioTemplateListResponse)
def list_education_templates() -> ScenarioTemplateListResponse:
    templates = scenario_template_service.list_templates(mode=SimulationMode.LEARNING)
    response_templates = [ScenarioTemplateResponse.model_validate(template.model_dump()) for template in templates]
    return ScenarioTemplateListResponse(templates=response_templates, count=len(response_templates))


@router.get("/scenarios/templates/{template_id}", response_model=ScenarioTemplateDetailResponse)
def get_education_template(template_id: str) -> ScenarioTemplateDetailResponse:
    try:
        template = scenario_template_service.get_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if template.mode != SimulationMode.LEARNING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning template '{template_id}' was not found.",
        )
    return ScenarioTemplateDetailResponse(template=ScenarioTemplateResponse.model_validate(template.model_dump()))


@router.post("/scenarios/templates/{template_id}/run", response_model=ScenarioTemplateRunResponse)
def run_education_template(
    template_id: str,
    payload: ScenarioTemplateRunRequest | None = None,
) -> ScenarioTemplateRunResponse:
    overrides = payload or ScenarioTemplateRunRequest()
    try:
        template, projection = scenario_template_service.run_template(
            template_id=template_id,
            base_world_id=overrides.base_world_id,
            projection_years=overrides.projection_years,
            mode=SimulationMode.LEARNING,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ScenarioTemplateRunResponse(
        template_id=template.template_id,
        template_name=template.name,
        objective=template.objective,
        product_focus=template.product_focus,
        projection_years=overrides.projection_years or template.default_projection_years,
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


@router.post("/simulation/project", response_model=ProjectFutureResponse)
def project_education_future(payload: ProjectFutureRequest) -> ProjectFutureResponse:
    try:
        actions = [
            SimulationAction(
                zone_id=action.zone_id,
                action_type=action_mapper.normalize_action_type(action.action_type),
                intensity=action.intensity,
                duration_years=action.duration_years,
            )
            for action in payload.actions
        ]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    world = world_service.get_world()
    if payload.base_world_id != world.world_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World '{payload.base_world_id}' was not found.",
        )

    projection = simulation_engine.project_world_result(
        base_world_id=payload.base_world_id,
        actions=actions,
        projection_years=payload.projection_years,
        mode=SimulationMode.LEARNING,
    )

    return ProjectFutureResponse(
        projection_years=payload.projection_years,
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


@router.post("/ai/explain", response_model=AIExplainResponse)
def explain_education_zone(payload: AIExplainRequest) -> AIExplainResponse:
    try:
        return ai_service.explain(
            zone_id=payload.zone_id,
            context=payload.context,
            question=payload.question,
            mode=SimulationMode.LEARNING,
            audience=payload.audience or AudienceType.STUDENT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
