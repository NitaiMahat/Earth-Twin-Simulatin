from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv  # type: ignore[import]
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Earth Twin Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    llm_explanations_enabled: bool = False
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "*")
    port: int = int(os.getenv("PORT", "8000"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    open_meteo_weather_url: str = os.getenv("OPEN_METEO_WEATHER_URL", "https://api.open-meteo.com/v1/forecast")
    open_meteo_air_quality_url: str = os.getenv(
        "OPEN_METEO_AIR_QUALITY_URL",
        "https://air-quality-api.open-meteo.com/v1/air-quality",
    )
    nominatim_reverse_url: str = os.getenv(
        "NOMINATIM_REVERSE_URL",
        "https://nominatim.openstreetmap.org/reverse",
    )
    public_data_user_agent: str = os.getenv(
        "PUBLIC_DATA_USER_AGENT",
        "EarthTwinBackend/0.1 (planning baseline lookup)",
    )
    public_data_timeout_seconds: float = float(os.getenv("PUBLIC_DATA_TIMEOUT_SECONDS", "2.5"))
    provider_cache_ttl_seconds: int = int(os.getenv("PROVIDER_CACHE_TTL_SECONDS", "3600"))
    database_url: str = os.getenv("DATABASE_URL", "")
    postgres_host: str = os.getenv("POSTGRES_HOST", "")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "earth_twin")
    postgres_user: str = os.getenv("POSTGRES_USER", "earth_twin")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "earth_twin")
    provider_cache_table_name: str = os.getenv("PROVIDER_CACHE_TABLE_NAME", "provider_cache_entries")
    provider_cache_connect_timeout_seconds: int = int(
        os.getenv("PROVIDER_CACHE_CONNECT_TIMEOUT_SECONDS", "3")
    )
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
    supabase_jwt_audience: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    supabase_jwt_issuer: str = os.getenv("SUPABASE_JWT_ISSUER", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_storage_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET", "project-reports")
    supabase_storage_public: bool = os.getenv("SUPABASE_STORAGE_PUBLIC", "false").lower() == "true"
    supabase_storage_signed_url_ttl_seconds: int = int(
        os.getenv("SUPABASE_STORAGE_SIGNED_URL_TTL_SECONDS", "3600")
    )

    @property
    def cors_origins(self) -> list[str]:
        normalized_value = self.cors_origins_raw.strip()
        if not normalized_value:
            return []
        if normalized_value == "*":
            return ["*"]
        return [origin.strip() for origin in normalized_value.split(",") if origin.strip()]

    @property
    def database_connection_url(self) -> str:
        direct_url = self.database_url.strip()
        if direct_url:
            return direct_url

        host = self.postgres_host.strip()
        if not host:
            return ""

        encoded_user = quote_plus(self.postgres_user)
        encoded_password = quote_plus(self.postgres_password)
        return (
            f"postgresql://{encoded_user}:{encoded_password}@{host}:{self.postgres_port}/{self.postgres_db}"
            f"?connect_timeout={self.provider_cache_connect_timeout_seconds}"
        )

    @property
    def provider_cache_database_url(self) -> str:
        return self.database_connection_url

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def seed_world_path(self) -> Path:
        return self.base_dir / "data" / "seed_world.json"

    @property
    def continents_path(self) -> Path:
        return self.base_dir / "data" / "continents.json"

    @property
    def scenario_templates_path(self) -> Path:
        return self.base_dir / "data" / "scenario_templates.json"

    @property
    def planning_site_path(self) -> Path:
        return self.base_dir / "data" / "planning_site.json"


settings = Settings()
