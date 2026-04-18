from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import ApplyActionRequest, CompareScenariosRequest, ProjectFutureRequest
from app.models.api.responses import (
    AppliedActionResponse,
    ApplyActionResponse,
    CompareScenariosResponse,
    ComparedScenarioResponse,
    MetricDeltaResponse,
    ProjectFutureResponse,
)
from app.models.domain.action import SimulationAction
from app.services.action_mapper import action_mapper
from app.services.impact_service import impact_service
from app.services.simulation_engine import simulation_engine

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/apply", response_model=ApplyActionResponse)
def apply_action(payload: ApplyActionRequest) -> ApplyActionResponse:
    try:
        normalized_action = action_mapper.normalize_action_type(payload.action_type)
        action = SimulationAction(
            zone_id=payload.zone_id,
            action_type=normalized_action,
            intensity=payload.intensity,
            duration_years=payload.duration_years,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    try:
        result = simulation_engine.apply_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    metric_delta = MetricDeltaResponse(
        tree_cover=result.derived_effects.tree_cover_delta,
        biodiversity_score=result.derived_effects.biodiversity_delta,
        pollution_level=result.derived_effects.pollution_delta,
        traffic_level=result.derived_effects.traffic_delta,
        temperature=result.derived_effects.temperature_delta,
        ecosystem_health=result.derived_effects.ecosystem_health_delta,
    )

    return ApplyActionResponse(
        zone_id=result.zone_id,
        requested_action_type=payload.action_type,
        normalized_action_type=result.action_type.value,
        mode=payload.mode,
        applied_action=AppliedActionResponse(
            action_type=result.action_type.value,
            intensity=payload.intensity,
            duration_years=payload.duration_years,
        ),
        before=result.before_state,
        after=result.after_state,
        delta=metric_delta,
        deltas=metric_delta,
        derived_effects=impact_service.build_metric_delta_messages(
            result.before_state,
            result.after_state,
        ),
        risk_level=result.risk_level.value,
        sustainability_score=result.after_state.sustainability_score,
        summary_text=impact_service.build_apply_summary(
            zone=result.after_state,
            requested_action_type=payload.action_type,
            normalized_action_type=result.action_type.value,
            mode=payload.mode,
        ),
        top_drivers=impact_service.build_top_drivers(result.after_state),
    )


@router.post("/project", response_model=ProjectFutureResponse)
def project_future(payload: ProjectFutureRequest) -> ProjectFutureResponse:
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

    try:
        projection = simulation_engine.project_world_result(
            base_world_id=payload.base_world_id,
            actions=actions,
            projection_years=payload.projection_years,
            mode=payload.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

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


@router.post("/compare", response_model=CompareScenariosResponse)
def compare_scenarios(payload: CompareScenariosRequest) -> CompareScenariosResponse:
    try:
        normalized_scenarios = [
            (
                scenario.name,
                [
                    SimulationAction(
                        zone_id=action.zone_id,
                        action_type=action_mapper.normalize_action_type(action.action_type),
                        intensity=action.intensity,
                        duration_years=action.duration_years,
                    )
                    for action in scenario.actions
                ],
            )
            for scenario in payload.scenarios
        ]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    try:
        comparison = simulation_engine.compare_scenarios(
            base_world_id=payload.base_world_id,
            projection_years=payload.projection_years,
            mode=payload.mode,
            scenarios=normalized_scenarios,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CompareScenariosResponse(
        mode=comparison.mode,
        projection_years=comparison.projection_years,
        scenarios=[
            ComparedScenarioResponse(
                name=scenario.name,
                summary=scenario.summary,
                summary_text=scenario.summary_text,
                highest_risk_zone=scenario.highest_risk_zone,
                avg_biodiversity_drop=scenario.avg_biodiversity_drop,
                avg_temperature_change=scenario.avg_temperature_change,
                sustainability_score=scenario.sustainability_score,
                overall_outlook=scenario.overall_outlook,
                recommended_focus=scenario.recommended_focus,
            )
            for scenario in comparison.scenarios
        ],
        recommended_scenario=comparison.recommended_scenario,
        key_tradeoffs=comparison.key_tradeoffs,
        comparison_summary_text=comparison.comparison_summary_text,
    )
