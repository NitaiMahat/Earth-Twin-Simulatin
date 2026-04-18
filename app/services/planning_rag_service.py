from __future__ import annotations

import re

from app.models.domain.planning import BuildSectionDefinition, InfrastructureCategory
from app.services.planning_service import planning_service

SUPPORTED_TEXT_INFRASTRUCTURE = (
    InfrastructureCategory.AIRPORT,
    InfrastructureCategory.ROAD,
)

UNSUPPORTED_KEYWORDS = {
    InfrastructureCategory.BRIDGE: ("bridge", "flyover", "overpass"),
    InfrastructureCategory.BUILDINGS: ("building", "buildings", "residential", "commercial", "tower"),
    InfrastructureCategory.GENERAL_AREA: ("district", "redevelopment", "site preparation", "land conversion"),
    InfrastructureCategory.SOLAR_PANEL: ("solar", "panel", "photovoltaic", "battery storage"),
}


class PlanningRagService:
    def _tokenize(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if token}

    def _supported_sections(self) -> list[BuildSectionDefinition]:
        return [planning_service.get_build_section_definition(infrastructure_type) for infrastructure_type in SUPPORTED_TEXT_INFRASTRUCTURE]

    def detect_unsupported_infrastructure(self, user_prompt: str) -> InfrastructureCategory | None:
        prompt = user_prompt.lower()
        for infrastructure_type, keywords in UNSUPPORTED_KEYWORDS.items():
            if any(keyword in prompt for keyword in keywords):
                return infrastructure_type
        return None

    def retrieve_context(self, user_prompt: str) -> dict[str, object]:
        prompt_tokens = self._tokenize(user_prompt)
        ranked_sections: list[tuple[int, BuildSectionDefinition]] = []

        for section in self._supported_sections():
            section_tokens = self._tokenize(
                " ".join(
                    [
                        section.infrastructure_type.value,
                        section.title,
                        section.summary,
                        section.default_project_type.value,
                        *(field.field_name for field in section.fields),
                        *(field.label for field in section.fields),
                        *(field.help_text for field in section.fields),
                    ]
                )
            )
            score = len(prompt_tokens & section_tokens)
            if section.infrastructure_type == InfrastructureCategory.AIRPORT and {"airport", "runway", "terminal", "apron"} & prompt_tokens:
                score += 3
            if section.infrastructure_type == InfrastructureCategory.ROAD and {"road", "roads", "lane", "highway", "corridor"} & prompt_tokens:
                score += 3
            ranked_sections.append((score, section))

        ranked_sections.sort(key=lambda item: item[0], reverse=True)
        selected_sections = [section for _, section in ranked_sections[:2]]
        context_parts: list[str] = []
        for section in selected_sections:
            required_fields = [field.field_name for field in section.fields if field.required]
            optional_fields = [field.field_name for field in section.fields if not field.required]
            context_parts.append(
                "\n".join(
                    [
                        f"Infrastructure type: {section.infrastructure_type.value}",
                        f"Default project type: {section.default_project_type.value}",
                        f"Summary: {section.summary}",
                        f"Required fields: {', '.join(required_fields)}",
                        f"Optional fields: {', '.join(optional_fields) if optional_fields else 'none'}",
                        f"Map instructions: {section.map_tool.instructions if section.map_tool else 'n/a'}",
                        f"Auto-derived fields: {', '.join(section.map_tool.auto_derived_fields) if section.map_tool else 'none'}",
                    ]
                )
            )

        top_score = ranked_sections[0][0] if ranked_sections else 0
        second_score = ranked_sections[1][0] if len(ranked_sections) > 1 else 0

        return {
            "selected_sections": selected_sections,
            "context_text": "\n\n".join(context_parts),
            "is_ambiguous": top_score == second_score,
            "top_score": top_score,
        }


planning_rag_service = PlanningRagService()
