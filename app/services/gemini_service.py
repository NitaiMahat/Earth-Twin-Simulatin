from __future__ import annotations

import json
import re
import time
from typing import Any

from app.core.config import settings

_MODEL = "gemini-2.5-flash"
_MAX_RETRIES = 3


class GeminiService:
    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai  # type: ignore[import]
            except ImportError as exc:
                raise RuntimeError(
                    "google-genai is not installed. Run: pip install google-genai"
                ) from exc
            api_key = settings.gemini_api_key
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY environment variable is not set. "
                    "Copy .env.example to .env and add your key."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _generate(self, prompt: str) -> str:
        """Call Gemini with automatic retry on 429 rate-limit errors."""
        client = self._get_client()
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=_MODEL,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                if "429" in err_str:
                    # Parse suggested retry delay from error message, default 65 s
                    delay = 65.0
                    match = re.search(r"retry in ([\d.]+)s", err_str)
                    if match:
                        delay = float(match.group(1)) + 2
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(delay)
                        continue
                raise RuntimeError(f"Gemini API error: {exc}") from exc

        raise RuntimeError(f"Gemini API failed after {_MAX_RETRIES} attempts: {last_exc}")

    def goal_to_actions(
        self,
        goal: str,
        zone_data: dict[str, Any],
        zone_id: str,
    ) -> list[dict[str, Any]]:
        zone_name = zone_data.get("name", zone_id)

        prompt = f"""You are an urban sustainability AI planner.

Goal: {goal}

Target zone: {zone_name}
Current environmental metrics:
- Traffic level: {zone_data.get('traffic_level', 0)}/100
- Pollution level: {zone_data.get('pollution_level', 0)}/100
- Tree cover: {zone_data.get('tree_cover', 0)}/100
- Biodiversity score: {zone_data.get('biodiversity_score', 0)}/100
- Ecosystem health: {zone_data.get('ecosystem_health', 0)}/100
- Risk level: {zone_data.get('risk_level', 'unknown')}

Allowed action types (use ONLY these exact strings):
- expand_roadway: boosts vehicle traffic capacity, worsens pollution
- add_urban_park: adds green space, cuts pollution, improves biodiversity
- improve_public_transit: reduces traffic congestion, lowers pollution
- restore_ecosystem: restores biodiversity, tree cover, and ecosystem health

Generate 2-4 actions that best achieve the stated goal given the zone's current state.

Return ONLY a valid JSON array. No markdown, no explanation, no code blocks.
Each object must have exactly: "action_type" (string), "intensity" (0.1-1.0), "duration_years" (1-10).

Example: [{{"action_type":"improve_public_transit","intensity":0.7,"duration_years":3}}]"""

        text = self._generate(prompt)
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        actions: list[dict[str, Any]] = json.loads(text)
        if not isinstance(actions, list):
            raise ValueError("Gemini returned a non-array response")
        return actions

    def suggest_improvements(
        self,
        goal: str,
        zone_name: str,
        actions: list[dict[str, Any]],
        initial_metrics: dict[str, Any],
        final_metrics: dict[str, Any],
        projection_years: int,
        sustainability_score: float,
        overall_outlook: str,
    ) -> str:
        actions_text = "\n".join(
            f"  * {a.get('action_type', '?').replace('_', ' ').title()}: "
            f"intensity {a.get('intensity', 0):.0%}, {a.get('duration_years', 1)} year(s)"
            for a in actions
        )
        initial_score = initial_metrics.get("sustainability_score", 0)
        temp_change = (
            final_metrics.get("temperature", 0) - initial_metrics.get("temperature", 0)
        )
        bio_change = (
            final_metrics.get("biodiversity_score", 0)
            - initial_metrics.get("biodiversity_score", 0)
        )

        prompt = f"""You are an urban sustainability expert writing a planning analysis report.

Goal: {goal}
Zone: {zone_name}
Projection period: {projection_years} years

Actions implemented:
{actions_text}

Simulation results:
- Sustainability score: {sustainability_score:.1f}/100 (was {initial_score:.1f}/100)
- Risk level after simulation: {final_metrics.get('risk_level', 'unknown')}
- Overall outlook: {overall_outlook}
- Temperature change: {temp_change:+.2f} C
- Biodiversity change: {bio_change:+.1f} points
- Final pollution level: {final_metrics.get('pollution_level', 0):.1f}/100
- Final tree cover: {final_metrics.get('tree_cover', 0):.1f}/100
- Final ecosystem health: {final_metrics.get('ecosystem_health', 0):.1f}/100

Write a sustainability analysis with these exact section headers:

EXECUTIVE SUMMARY
[2-3 sentences summarizing outcomes vs the stated goal]

KEY FINDINGS
* [data-backed finding]
* [data-backed finding]
* [data-backed finding]
* [data-backed finding]

IMPROVEMENT RECOMMENDATIONS
1. [Specific actionable recommendation]
2. [Specific actionable recommendation]
3. [Specific actionable recommendation]
4. [Specific actionable recommendation]

LONG-TERM OUTLOOK
[1-2 sentences on the 10-20 year trajectory if this plan is sustained]

Be specific and reference the actual numbers from the simulation results."""

        return self._generate(prompt)


gemini_service = GeminiService()
