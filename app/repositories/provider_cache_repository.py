from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency in local test environments
    psycopg = None


@dataclass(frozen=True)
class ProviderCacheSnapshot:
    key: str
    value: Any
    expires_at: datetime


class ProviderCacheRepository:
    def __init__(self, database_url: str, table_name: str = "provider_cache_entries") -> None:
        self._database_url = database_url.strip()
        self._table_name = table_name
        self._schema_ready = False

    @property
    def enabled(self) -> bool:
        return bool(self._database_url) and psycopg is not None

    def _connect(self) -> Any | None:
        if not self.enabled:
            return None
        try:
            return psycopg.connect(self._database_url, autocommit=True)
        except Exception:
            return None

    def ensure_ready(self) -> bool:
        if self._schema_ready:
            return True

        connection = self._connect()
        if connection is None:
            return False

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        cache_key TEXT PRIMARY KEY,
                        payload JSONB NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{self._table_name}_expires_at
                    ON {self._table_name} (expires_at)
                    """
                )
            self._schema_ready = True
            return True
        except Exception:
            return False
        finally:
            connection.close()

    def get(self, key: str) -> ProviderCacheSnapshot | None:
        if not self.ensure_ready():
            return None

        connection = self._connect()
        if connection is None:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT payload, expires_at FROM {self._table_name} WHERE cache_key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None

                payload, expires_at = row
                if not isinstance(expires_at, datetime):
                    return None
                if expires_at <= datetime.now(UTC):
                    cursor.execute(f"DELETE FROM {self._table_name} WHERE cache_key = %s", (key,))
                    return None

                return ProviderCacheSnapshot(key=key, value=payload, expires_at=expires_at.astimezone(UTC))
        except Exception:
            return None
        finally:
            connection.close()

    def set(self, key: str, value: Any, ttl_seconds: int) -> bool:
        if not self.ensure_ready():
            return False

        connection = self._connect()
        if connection is None:
            return False

        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {self._table_name} (cache_key, payload, expires_at)
                    VALUES (%s, %s::jsonb, %s)
                    ON CONFLICT (cache_key)
                    DO UPDATE SET
                        payload = EXCLUDED.payload,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, json.dumps(value), expires_at),
                )
            return True
        except Exception:
            return False
        finally:
            connection.close()
