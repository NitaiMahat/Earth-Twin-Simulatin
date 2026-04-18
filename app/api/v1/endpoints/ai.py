from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import (
    AIExplainRequest,
    GoalToActionsRequest,
    SuggestImprovementsRequest,
)
from app.models.api.responses import (
    AIExplainResponse,
    GoalActionItem,
    GoalToActionsResponse,
    SuggestImprovementsResponse,
)
from app.repositories.zone_repository import zone_repository
from app.services.ai_service import ai_service
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/explain", response_model=AIExplainResponse)
def explain_zone(payload: AIExplainRequest) -> AIExplainResponse:
    try:
        return ai_service.explain(
            zone_id=payload.zone_id,
            context=payload.context,
            question=payload.question,
            mode=payload.mode,
            audience=payload.audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/goal-to-actions", response_model=GoalToActionsResponse)
def goal_to_actions(payload: GoalToActionsRequest) -> GoalToActionsResponse:
    zone = zone_repository.get_zone(payload.zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{payload.zone_id}' not found.",
        )

    zone_data = zone.model_dump()

    try:
        raw_actions = gemini_service.goal_to_actions(
            goal=payload.goal,
            zone_data=zone_data,
            zone_id=payload.zone_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Gemini returned invalid actions: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        actions = [
            GoalActionItem(
                action_type=str(a.get("action_type", "")),
                intensity=float(a.get("intensity", 0.5)),
                duration_years=int(a.get("duration_years", 3)),
            )
            for a in raw_actions
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse Gemini response: {exc}",
        ) from exc

    return GoalToActionsResponse(
        goal=payload.goal,
        zone_id=payload.zone_id,
        actions=actions,
    )


@router.post("/suggest-improvements", response_model=SuggestImprovementsResponse)
def suggest_improvements(payload: SuggestImprovementsRequest) -> SuggestImprovementsResponse:
    try:
        analysis = gemini_service.suggest_improvements(
            goal=payload.goal,
            zone_name=payload.zone_name,
            actions=payload.actions,
            initial_metrics=payload.initial_metrics,
            final_metrics=payload.final_metrics,
            projection_years=payload.projection_years,
            sustainability_score=payload.sustainability_score,
            overall_outlook=payload.overall_outlook,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return SuggestImprovementsResponse(analysis=analysis)
