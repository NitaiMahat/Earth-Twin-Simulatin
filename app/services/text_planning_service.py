from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.models.api.requests import TextPlanningOverridesRequest
from app.models.api.responses import (
    PlanningLocationContextResponse,
    TextPlanningExtractionResponse,
    TextPlanningRunResponse,
)
from app.models.domain.planning import (
    BuildFieldDefinition,
    GeometryPoint,
    InfrastructureCategory,
    MitigationCommitment,
    PlannerProjectType,
    PlanningLocationInput,
)
from app.services.gemini_service import gemini_service
from app.services.planning_rag_service import planning_rag_service
from app.services.planning_service import planning_service
from app.services.public_baseline_service import public_baseline_service

TEXT_PLANNING_CONFIDENCE_THRESHOLD = 0.65
TEXT_PLANNING_GEOMETRY_TYPE = InfrastructureCategory.ROAD


class TextPlanningService:
    def _location_context_response(self, location: PlanningLocationInput) -> PlanningLocationContextResponse:
        context = public_baseline_service.build_location_context(location)
        return PlanningLocationContextResponse.model_validate(context.model_dump())

    def _coerce_field_value(self, field: BuildFieldDefinition, value: Any) -> str | int | float | bool | None:
        if value is None:
            return None
        if field.field_type.value == "text":
            text = str(value).strip()
            return text or None

        if isinstance(value, bool):
            raise ValueError(f"Field '{field.field_name}' must be numeric.")

        numeric_value: float
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str) and value.strip():
            try:
                numeric_value = float(value.strip())
            except ValueError:
                return None
        else:
            return None

        if field.field_type.value == "integer":
            return int(round(numeric_value))
        return round(numeric_value, 2)

    def _normalize_details(
        self,
        infrastructure_type: InfrastructureCategory,
        raw_details: dict[str, Any],
    ) -> dict[str, str | int | float | bool]:
        section = planning_service.get_build_section_definition(infrastructure_type)
        normalized: dict[str, str | int | float | bool] = {}
        for field in section.fields:
            if field.field_name not in raw_details:
                continue
            coerced_value = self._coerce_field_value(field, raw_details.get(field.field_name))
            if coerced_value is not None:
                normalized[field.field_name] = coerced_value
        return normalized

    def _merge_geometry_details(
        self,
        infrastructure_type: InfrastructureCategory,
        details: dict[str, str | int | float | bool],
        geometry_summary: Any,
    ) -> dict[str, str | int | float | bool]:
        derived_only = planning_service.merge_geometry_details(infrastructure_type, {}, geometry_summary)
        return {**details, **derived_only}

    def _missing_required_fields(
        self,
        infrastructure_type: InfrastructureCategory,
        details: dict[str, str | int | float | bool],
    ) -> list[str]:
        section = planning_service.get_build_section_definition(infrastructure_type)
        missing: list[str] = []
        for field in section.fields:
            if not field.required:
                continue
            value = details.get(field.field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field.field_name)
        return missing

    def _resolve_infrastructure_type(self, raw_type: Any) -> InfrastructureCategory | None:
        if raw_type is None:
            return None
        normalized = str(raw_type).strip()
        if not normalized:
            return None
        if normalized == "unsupported":
            raise ValueError("Only airport and road text planning is supported in v1.")
        infrastructure_type = InfrastructureCategory(normalized)
        if infrastructure_type not in {InfrastructureCategory.AIRPORT, InfrastructureCategory.ROAD}:
            raise ValueError("Only airport and road text planning is supported in v1.")
        return infrastructure_type

    def _resolve_project_type(
        self,
        infrastructure_type: InfrastructureCategory | None,
        raw_project_type: Any,
    ) -> PlannerProjectType | None:
        if infrastructure_type is not None:
            return planning_service.get_build_section_definition(infrastructure_type).default_project_type
        if raw_project_type is None:
            return None
        return PlannerProjectType(str(raw_project_type))

    def _build_draft(
        self,
        *,
        location: PlanningLocationInput,
        geometry_points: list[GeometryPoint],
        user_prompt: str,
    ) -> TextPlanningExtractionResponse:
        unsupported_infrastructure = planning_rag_service.detect_unsupported_infrastructure(user_prompt)
        if unsupported_infrastructure is not None:
            raise ValueError(
                f"Text planning currently supports only airport and road prompts. Detected unsupported type "
                f"'{unsupported_infrastructure.value}'."
            )

        location_context = self._location_context_response(location)
        geometry_summary = planning_service.build_geometry_summary(TEXT_PLANNING_GEOMETRY_TYPE, geometry_points)
        retrieval = planning_rag_service.retrieve_context(user_prompt)
        extracted = gemini_service.extract_text_plan(
            user_prompt=user_prompt,
            retrieved_context=str(retrieval["context_text"]),
            location_label=location_context.label,
            geometry_summary=geometry_summary.model_dump(mode="json"),
        )

        infrastructure_type = self._resolve_infrastructure_type(extracted.get("infrastructure_type"))
        project_type = self._resolve_project_type(infrastructure_type, extracted.get("project_type"))
        planner_summary = str(extracted.get("planner_summary") or user_prompt).strip()
        assumptions = list(extracted.get("assumptions", []))
        confidence = float(extracted.get("confidence", 0.0))

        merged_details: dict[str, str | int | float | bool] = {}
        backend_missing_fields: list[str] = []
        footprint_acres: float | None = None
        estimated_daily_vehicle_trips: int | None = None
        buildout_years: int | None = None

        if infrastructure_type is not None:
            normalized_details = self._normalize_details(
                infrastructure_type,
                dict(extracted.get("infrastructure_details", {})),
            )
            merged_details = self._merge_geometry_details(infrastructure_type, normalized_details, geometry_summary)
            backend_missing_fields = self._missing_required_fields(infrastructure_type, merged_details)

            estimated_daily_vehicle_trips_value = merged_details.get("daily_vehicle_trips")
            if isinstance(estimated_daily_vehicle_trips_value, int):
                estimated_daily_vehicle_trips = estimated_daily_vehicle_trips_value

            construction_years_value = merged_details.get("construction_years")
            if isinstance(construction_years_value, int):
                buildout_years = construction_years_value

            if not backend_missing_fields:
                (
                    project_type,
                    resolved_details,
                    resolved_footprint_acres,
                    resolved_estimated_daily_vehicle_trips,
                    resolved_buildout_years,
                ) = planning_service.resolve_infrastructure_inputs(infrastructure_type, merged_details)
                merged_details = resolved_details
                footprint_acres = round(resolved_footprint_acres, 2)
                estimated_daily_vehicle_trips = resolved_estimated_daily_vehicle_trips
                buildout_years = resolved_buildout_years

        missing_fields = list(dict.fromkeys([
            *(str(field) for field in extracted.get("missing_fields", [])),
            *backend_missing_fields,
        ]))
        if infrastructure_type is None and "infrastructure_type" not in missing_fields:
            missing_fields.append("infrastructure_type")

        if confidence < TEXT_PLANNING_CONFIDENCE_THRESHOLD:
            assumptions.append("The prompt is low-confidence and should be confirmed before running the simulation.")

        simulation_ready = (
            infrastructure_type is not None
            and not missing_fields
            and confidence >= TEXT_PLANNING_CONFIDENCE_THRESHOLD
        )

        return TextPlanningExtractionResponse(
            location_context=location_context,
            geometry_summary=geometry_summary,
            infrastructure_type=infrastructure_type,
            project_type=project_type,
            planner_summary=planner_summary,
            infrastructure_details=merged_details,
            footprint_acres=footprint_acres,
            estimated_daily_vehicle_trips=estimated_daily_vehicle_trips,
            buildout_years=buildout_years,
            missing_fields=missing_fields,
            assumptions=list(dict.fromkeys(assumptions)),
            confidence=round(confidence, 2),
            simulation_ready=simulation_ready,
        )

    def draft_from_text(
        self,
        *,
        location: PlanningLocationInput,
        geometry_points: list[GeometryPoint],
        user_prompt: str,
    ) -> TextPlanningExtractionResponse:
        return self._build_draft(
            location=location,
            geometry_points=geometry_points,
            user_prompt=user_prompt,
        )

    def run_from_text(
        self,
        *,
        location: PlanningLocationInput,
        geometry_points: list[GeometryPoint],
        user_prompt: str,
        mitigation_commitment: MitigationCommitment,
        confirmed_overrides: TextPlanningOverridesRequest | None,
        planner_notes: str | None,
    ) -> TextPlanningRunResponse:
        draft = self._build_draft(
            location=location,
            geometry_points=geometry_points,
            user_prompt=user_prompt,
        )

        override_payload = confirmed_overrides or TextPlanningOverridesRequest()
        infrastructure_type = override_payload.infrastructure_type or draft.infrastructure_type
        if infrastructure_type is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "The prompt was too ambiguous to choose airport vs road. Confirm the infrastructure type first.",
                    "missing_fields": ["infrastructure_type"],
                },
            )

        if draft.confidence < TEXT_PLANNING_CONFIDENCE_THRESHOLD and override_payload.infrastructure_type is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "The prompt is low-confidence. Confirm the infrastructure type before running.",
                    "missing_fields": ["infrastructure_type"],
                },
            )

        geometry_summary = planning_service.build_geometry_summary(infrastructure_type, geometry_points)
        merged_details = dict(draft.infrastructure_details)
        merged_details.update(override_payload.infrastructure_details)
        merged_details = self._normalize_details(infrastructure_type, merged_details)
        merged_details = self._merge_geometry_details(infrastructure_type, merged_details, geometry_summary)

        missing_fields = self._missing_required_fields(infrastructure_type, merged_details)
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Missing required fields for simulation.",
                    "missing_fields": missing_fields,
                },
            )

        assessment = planning_service.assess_proposal(
            location=location,
            project_type=None,
            infrastructure_type=infrastructure_type,
            geometry_points=geometry_points,
            infrastructure_details=merged_details,
            footprint_acres=override_payload.footprint_acres or draft.footprint_acres,
            estimated_daily_vehicle_trips=(
                override_payload.estimated_daily_vehicle_trips or draft.estimated_daily_vehicle_trips
            ),
            buildout_years=override_payload.buildout_years or draft.buildout_years,
            mitigation_commitment=mitigation_commitment,
            planner_notes=planner_notes,
        )

        extraction = TextPlanningExtractionResponse(
            location_context=draft.location_context,
            geometry_summary=geometry_summary,
            infrastructure_type=infrastructure_type,
            project_type=assessment.project_type,
            planner_summary=draft.planner_summary,
            infrastructure_details=assessment.infrastructure_details,
            footprint_acres=assessment.footprint_acres,
            estimated_daily_vehicle_trips=assessment.estimated_daily_vehicle_trips,
            buildout_years=assessment.buildout_years,
            missing_fields=[],
            assumptions=draft.assumptions,
            confidence=draft.confidence,
            simulation_ready=True,
        )
        return TextPlanningRunResponse(extraction=extraction, assessment=assessment)


text_planning_service = TextPlanningService()
