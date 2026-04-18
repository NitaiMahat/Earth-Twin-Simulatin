from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.api.requests import GenerateReportRequest
from app.services.gemini_service import gemini_service
from app.services.report_service import generate_pdf_report

router = APIRouter(prefix="/simulation", tags=["report"])


@router.post("/report")
def generate_report(payload: GenerateReportRequest) -> StreamingResponse:
    ai_analysis = payload.ai_analysis.strip()

    if not ai_analysis:
        try:
            ai_analysis = gemini_service.suggest_improvements(
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

    try:
        pdf_bytes = generate_pdf_report(
            goal=payload.goal,
            zone_name=payload.zone_name,
            zone_type=payload.zone_type,
            actions=payload.actions,
            initial_metrics=payload.initial_metrics,
            final_metrics=payload.final_metrics,
            projection_years=payload.projection_years,
            sustainability_score=payload.sustainability_score,
            overall_outlook=payload.overall_outlook,
            ai_analysis=ai_analysis,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        ) from exc

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="earth-twin-sustainability-report.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
