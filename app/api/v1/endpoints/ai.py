from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.api.requests import AIExplainRequest
from app.models.api.responses import AIExplainResponse
from app.services.ai_service import ai_service

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
