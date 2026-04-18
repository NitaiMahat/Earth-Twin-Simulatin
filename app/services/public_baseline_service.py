from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.models.domain.continent import ContinentDefinition
from app.models.domain.planning import PlanningLocationContext, PlanningLocationInput
from app.models.domain.world import WorldState
from app.models.domain.zone import ZoneState, ZoneType
from app.repositories.provider_cache_repository import ProviderCacheRepository

FOREST_AREA_INDICATOR = "AG.LND.FRST.ZS"
POPULATION_DENSITY_INDICATOR = "EN.POP.DNST"
GLOBAL_WORLD_ID = "global_continental_baseline"
GLOBAL_WORLD_NAME = "Earth Twin Global Continents"
ISO2_TO_ISO3 = {
    "AU": "AUS",
    "BR": "BRA",
    "CA": "CAN",
    "CN": "CHN",
    "DE": "DEU",
    "FR": "FRA",
    "GB": "GBR",
    "IN": "IND",
    "JP": "JPN",
    "MX": "MEX",
    "NG": "NGA",
    "RU": "RUS",
    "US": "USA",
    "ZA": "ZAF",
}


class PublicBaselineService:
    def __init__(self) -> None:
        self._continents = self._load_continents()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._persistent_cache = ProviderCacheRepository(
            settings.provider_cache_database_url,
            settings.provider_cache_table_name,
        )

    def _load_continents(self) -> list[ContinentDefinition]:
        with settings.continents_path.open("r", encoding="utf-8") as continents_file:
            payload = json.load(continents_file)
        return [ContinentDefinition.model_validate(item) for item in payload]

    def list_continents(self) -> list[ContinentDefinition]:
        return self._continents

    def get_continent(self, continent_id: str) -> ContinentDefinition:
        for continent in self._continents:
            if continent.continent_id == continent_id:
                return continent
        raise ValueError(f"Continent '{continent_id}' was not found.")

    def resolve_continent(self, latitude: float, longitude: float) -> ContinentDefinition:
        if latitude <= -60:
            return self.get_continent("antarctica")
        if -35 <= latitude <= 37 and -20 <= longitude <= 55:
            return self.get_continent("africa")
        if 5 <= latitude <= 82 and 25 <= longitude <= 180:
            return self.get_continent("asia")
        if 35 <= latitude <= 72 and -25 <= longitude <= 60:
            return self.get_continent("europe")
        if 7 <= latitude <= 84 and (-170 <= longitude <= -50):
            return self.get_continent("north_america")
        if -56 <= latitude <= 13 and -82 <= longitude <= -34:
            return self.get_continent("south_america")
        if -50 <= latitude <= 5 and 110 <= longitude <= 180:
            return self.get_continent("oceania")

        return min(
            self._continents,
            key=lambda continent: ((continent.latitude - latitude) ** 2) + ((continent.longitude - longitude) ** 2),
        )

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _cache_get(self, key: str) -> Any | None:
        cached_entry = self._cache.get(key)
        if cached_entry is None:
            snapshot = self._persistent_cache.get(key)
            if snapshot is None:
                return None

            remaining_seconds = max(snapshot.expires_at.timestamp() - time.time(), 1.0)
            self._cache[key] = (time.time() + remaining_seconds, snapshot.value)
            return snapshot.value

        expires_at, value = cached_entry
        if expires_at < time.time():
            self._cache.pop(key, None)
            snapshot = self._persistent_cache.get(key)
            if snapshot is None:
                return None

            remaining_seconds = max(snapshot.expires_at.timestamp() - time.time(), 1.0)
            self._cache[key] = (time.time() + remaining_seconds, snapshot.value)
            return snapshot.value
        return value

    def _cache_set(self, key: str, value: Any, ttl_seconds: int | None = None) -> Any:
        ttl = ttl_seconds or settings.provider_cache_ttl_seconds
        self._cache[key] = (time.time() + ttl, value)
        self._persistent_cache.set(key, value, ttl)
        return value

    def _coordinate_key(self, latitude: float, longitude: float) -> str:
        return f"{round(latitude, 3):.3f},{round(longitude, 3):.3f}"

    def _request_json(self, url: str, params: dict[str, Any]) -> Any | None:
        try:
            with httpx.Client(
                timeout=settings.public_data_timeout_seconds,
                headers={"User-Agent": settings.public_data_user_agent},
            ) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def _normalize_series_response(self, payload: Any) -> list[dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []

    def _fetch_weather_batch(self, points: list[tuple[str, float, float]]) -> dict[str, float]:
        uncached_points: list[tuple[str, float, float]] = []
        results: dict[str, float] = {}
        for point in points:
            cache_key = f"weather:{self._coordinate_key(point[1], point[2])}"
            cached = self._cache_get(cache_key)
            if isinstance(cached, (int, float)):
                results[point[0]] = round(float(cached), 2)
            else:
                uncached_points.append(point)

        if uncached_points:
            payload = self._request_json(
                settings.open_meteo_weather_url,
                {
                    "latitude": ",".join(str(point[1]) for point in uncached_points),
                    "longitude": ",".join(str(point[2]) for point in uncached_points),
                    "current": "temperature_2m",
                    "timezone": "GMT",
                },
            )
        else:
            payload = None

        for point, item in zip(uncached_points, self._normalize_series_response(payload), strict=False):
            current = item.get("current", {})
            temperature = current.get("temperature_2m")
            if isinstance(temperature, (int, float)):
                rounded_temperature = round(float(temperature), 2)
                results[point[0]] = rounded_temperature
                self._cache_set(f"weather:{self._coordinate_key(point[1], point[2])}", rounded_temperature)
        return results

    def _fetch_air_quality_batch(self, points: list[tuple[str, float, float]]) -> dict[str, float]:
        uncached_points: list[tuple[str, float, float]] = []
        results: dict[str, float] = {}
        for point in points:
            cache_key = f"air_quality:{self._coordinate_key(point[1], point[2])}"
            cached = self._cache_get(cache_key)
            if isinstance(cached, (int, float)):
                results[point[0]] = round(float(cached), 2)
            else:
                uncached_points.append(point)

        if uncached_points:
            payload = self._request_json(
                settings.open_meteo_air_quality_url,
                {
                    "latitude": ",".join(str(point[1]) for point in uncached_points),
                    "longitude": ",".join(str(point[2]) for point in uncached_points),
                    "current": "us_aqi",
                    "timezone": "GMT",
                },
            )
        else:
            payload = None

        for point, item in zip(uncached_points, self._normalize_series_response(payload), strict=False):
            current = item.get("current", {})
            us_aqi = current.get("us_aqi")
            if isinstance(us_aqi, (int, float)):
                rounded_aqi = round(float(us_aqi), 2)
                results[point[0]] = rounded_aqi
                self._cache_set(f"air_quality:{self._coordinate_key(point[1], point[2])}", rounded_aqi)
        return results

    def _fetch_world_bank_indicator(self, country_codes: list[str], indicator: str) -> dict[str, float]:
        if not country_codes:
            return {}

        normalized_codes = sorted(set(country_codes))
        cache_key = f"world_bank:{indicator}:{';'.join(normalized_codes)}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

        payload = self._request_json(
            f"https://api.worldbank.org/v2/country/{';'.join(normalized_codes)}/indicator/{indicator}",
            {"format": "json", "per_page": 200},
        )
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            return {}

        latest_by_country: dict[str, float] = {}
        for row in payload[1]:
            if not isinstance(row, dict):
                continue
            country_code = row.get("countryiso3code")
            value = row.get("value")
            if not isinstance(country_code, str) or not isinstance(value, (int, float)):
                continue
            if country_code not in latest_by_country:
                latest_by_country[country_code] = round(float(value), 2)
        return self._cache_set(cache_key, latest_by_country)

    def _reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        cache_key = f"reverse_geocode:{self._coordinate_key(latitude, longitude)}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

        payload = self._request_json(
            settings.nominatim_reverse_url,
            {
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "addressdetails": 1,
                "zoom": 10,
            },
        )
        if not isinstance(payload, dict):
            payload = {}
        return self._cache_set(cache_key, payload)

    def _extract_location_label(self, reverse_payload: dict[str, Any], fallback_label: str) -> str:
        address = reverse_payload.get("address", {})
        if not isinstance(address, dict):
            return fallback_label
        pieces = [
            address.get("city"),
            address.get("town"),
            address.get("state"),
            address.get("country"),
        ]
        label = ", ".join(str(piece).strip() for piece in pieces if isinstance(piece, str) and piece.strip())
        return label or fallback_label

    def _extract_country_code(self, reverse_payload: dict[str, Any]) -> str | None:
        address = reverse_payload.get("address", {})
        if not isinstance(address, dict):
            return None
        country_code = address.get("country_code")
        if isinstance(country_code, str) and country_code.strip():
            normalized = country_code.strip().upper()
            return ISO2_TO_ISO3.get(normalized, normalized)
        return None

    def _extract_country_name(self, reverse_payload: dict[str, Any]) -> str | None:
        address = reverse_payload.get("address", {})
        if not isinstance(address, dict):
            return None
        country = address.get("country")
        if isinstance(country, str) and country.strip():
            return country.strip()
        return None

    def _extract_state_name(self, reverse_payload: dict[str, Any]) -> str | None:
        address = reverse_payload.get("address", {})
        if not isinstance(address, dict):
            return None
        for key in ("state", "region", "county"):
            value = address.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _temperature_comfort_score(self, temperature: float) -> float:
        return max(0.0, min(100.0, 100.0 - (abs(temperature - 18.0) * 4.5)))

    def _fallback_natural_cover(self, latitude: float, pollution_level: float) -> float:
        return max(10.0, min(90.0, 82.0 - (abs(latitude) * 0.4) - (pollution_level * 0.18)))

    def _normalize_pollution(self, us_aqi: float) -> float:
        return max(0.0, min(100.0, round(us_aqi / 2.5, 2)))

    def _normalize_traffic(self, population_density: float | None, pollution_level: float) -> float:
        if population_density is None:
            return max(5.0, min(100.0, round((pollution_level * 0.55) + 15.0, 2)))
        return max(0.0, min(100.0, round(math.log10(max(population_density, 1.0)) * 25.0, 2)))

    def _build_zone(
        self,
        zone_id: str,
        name: str,
        latitude: float,
        longitude: float,
        reference_country_code: str | None,
        temperature: float,
        us_aqi: float,
        forest_area_pct: float | None,
        population_density: float | None,
        source_summary: str,
    ) -> ZoneState:
        pollution_level = self._normalize_pollution(us_aqi)
        tree_cover = round(
            forest_area_pct if forest_area_pct is not None else self._fallback_natural_cover(latitude, pollution_level),
            2,
        )
        traffic_level = self._normalize_traffic(population_density, pollution_level)
        biodiversity_score = max(
            0.0,
            min(
                100.0,
                round((tree_cover * 0.62) + ((100.0 - pollution_level) * 0.23) + ((100.0 - traffic_level) * 0.15), 2),
            ),
        )
        ecosystem_health = max(
            0.0,
            min(
                100.0,
                round(
                    (tree_cover * 0.33)
                    + (biodiversity_score * 0.37)
                    + ((100.0 - pollution_level) * 0.2)
                    + (self._temperature_comfort_score(temperature) * 0.1),
                    2,
                ),
            ),
        )

        return ZoneState(
            zone_id=zone_id,
            name=name,
            type=ZoneType.CONTINENT,
            scope="continent",
            latitude=latitude,
            longitude=longitude,
            reference_country_code=reference_country_code,
            source_summary=source_summary,
            tree_cover=tree_cover,
            biodiversity_score=biodiversity_score,
            pollution_level=pollution_level,
            traffic_level=traffic_level,
            temperature=round(temperature, 2),
            ecosystem_health=ecosystem_health,
        )

    def build_world(self) -> WorldState:
        points = [(continent.continent_id, continent.latitude, continent.longitude) for continent in self._continents]
        weather_by_continent = self._fetch_weather_batch(points)
        aqi_by_continent = self._fetch_air_quality_batch(points)

        country_codes = [continent.representative_country_code for continent in self._continents if continent.representative_country_code]
        forest_by_country = self._fetch_world_bank_indicator(country_codes, FOREST_AREA_INDICATOR)
        density_by_country = self._fetch_world_bank_indicator(country_codes, POPULATION_DENSITY_INDICATOR)

        zones: list[ZoneState] = []
        for continent in self._continents:
            temperature = weather_by_continent.get(continent.continent_id, 16.0 - (abs(continent.latitude) * 0.12))
            us_aqi = aqi_by_continent.get(continent.continent_id, 45.0)
            forest_area_pct = (
                forest_by_country.get(continent.representative_country_code)
                if continent.representative_country_code is not None
                else None
            )
            population_density = (
                density_by_country.get(continent.representative_country_code)
                if continent.representative_country_code is not None
                else None
            )
            source_summary = (
                "Dynamic public baseline using Open-Meteo weather and air quality plus latest World Bank land-density indicators where available."
            )
            zones.append(
                self._build_zone(
                    zone_id=continent.zone_id,
                    name=continent.name,
                    latitude=continent.latitude,
                    longitude=continent.longitude,
                    reference_country_code=continent.representative_country_code,
                    temperature=temperature,
                    us_aqi=us_aqi,
                    forest_area_pct=forest_area_pct,
                    population_density=population_density,
                    source_summary=source_summary,
                )
            )

        global_temperature = round(sum(zone.temperature for zone in zones) / len(zones), 2)
        global_co2_index = round(360.0 + (sum(zone.pollution_level for zone in zones) / len(zones) * 1.2), 2)
        return WorldState(
            world_id=GLOBAL_WORLD_ID,
            name=GLOBAL_WORLD_NAME,
            baseline_mode="dynamic_public",
            current_year=datetime.now(UTC).year,
            global_temperature=global_temperature,
            global_co2_index=global_co2_index,
            zones=zones,
        )

    def build_location_context(self, location: PlanningLocationInput) -> PlanningLocationContext:
        continent = self.resolve_continent(location.latitude, location.longitude)
        reverse_payload = self._reverse_geocode(location.latitude, location.longitude)
        fallback_label = location.label or f"Selected location in {continent.name}"
        label = location.label or self._extract_location_label(reverse_payload, fallback_label)
        country_code = (
            location.country_code
            or self._extract_country_code(reverse_payload)
            or continent.representative_country_code
        )
        country_name = self._extract_country_name(reverse_payload)
        state_name = self._extract_state_name(reverse_payload)
        return PlanningLocationContext(
            label=label,
            latitude=location.latitude,
            longitude=location.longitude,
            continent_id=continent.continent_id,
            continent_name=continent.name,
            baseline_zone_id=continent.zone_id,
            country_code=country_code,
            country_name=country_name,
            state_name=state_name,
            source_summary=(
                "Location context resolved from coordinates using continent mapping plus cached Nominatim reverse geocoding when available."
            ),
        )

    def build_location_zone(self, location: PlanningLocationInput) -> tuple[PlanningLocationContext, ZoneState]:
        context = self.build_location_context(location)
        temperature = self._fetch_weather_batch([("location", location.latitude, location.longitude)]).get("location")
        us_aqi = self._fetch_air_quality_batch([("location", location.latitude, location.longitude)]).get("location")

        forest_area_pct: float | None = None
        population_density: float | None = None
        if context.country_code is not None:
            forest_area_pct = self._fetch_world_bank_indicator([context.country_code], FOREST_AREA_INDICATOR).get(
                context.country_code
            )
            population_density = self._fetch_world_bank_indicator([context.country_code], POPULATION_DENSITY_INDICATOR).get(
                context.country_code
            )

        continent = self.get_continent(context.continent_id)
        zone = self._build_zone(
            zone_id=context.baseline_zone_id,
            name=context.label,
            latitude=location.latitude,
            longitude=location.longitude,
            reference_country_code=context.country_code,
            temperature=temperature if temperature is not None else continent.latitude * -0.05 + 18.0,
            us_aqi=us_aqi if us_aqi is not None else 50.0,
            forest_area_pct=forest_area_pct,
            population_density=population_density,
            source_summary=(
                "Location baseline built from live Open-Meteo conditions and latest World Bank country indicators when available."
            ),
        )
        return context, zone


public_baseline_service = PublicBaselineService()
