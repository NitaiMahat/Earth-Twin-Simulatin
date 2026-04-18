from __future__ import annotations

import json
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


class ProjectSnapshotRepository:
    def __init__(self, database_url: str, table_name: str = "user_project_snapshots") -> None:
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
                        project_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        user_email TEXT,
                        project_name TEXT NOT NULL,
                        continent_id TEXT NOT NULL,
                        project_type TEXT NOT NULL,
                        infrastructure_type TEXT,
                        location_label TEXT NOT NULL,
                        recommended_option TEXT NOT NULL,
                        assessment_payload JSONB NOT NULL,
                        text_planning_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        latest_report_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    f"""
                    ALTER TABLE {self._table_name}
                    ADD COLUMN IF NOT EXISTS text_planning_payload JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    """
                )
                cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{self._table_name}_user_updated
                    ON {self._table_name} (user_id, updated_at DESC)
                    """
                )
            self._schema_ready = True
            return True
        except Exception:
            return False
        finally:
            connection.close()

    def create_project(self, record: dict[str, Any]) -> dict[str, Any] | None:
        if not self.ensure_ready():
            return None

        connection = self._connect()
        if connection is None:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {self._table_name} (
                        project_id,
                        user_id,
                        user_email,
                        project_name,
                        continent_id,
                        project_type,
                        infrastructure_type,
                        location_label,
                        recommended_option,
                        assessment_payload,
                        text_planning_payload,
                        latest_report_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                    RETURNING project_id, user_id, user_email, project_name, continent_id, project_type,
                        infrastructure_type, location_label, recommended_option, assessment_payload,
                        text_planning_payload, latest_report_payload, created_at, updated_at
                    """,
                    (
                        record["project_id"],
                        record["user_id"],
                        record.get("user_email"),
                        record["project_name"],
                        record["continent_id"],
                        record["project_type"],
                        record.get("infrastructure_type"),
                        record["location_label"],
                        record["recommended_option"],
                        json.dumps(record["assessment_payload"]),
                        json.dumps(record.get("text_planning_payload", {})),
                        json.dumps(record.get("latest_report_payload", {})),
                    ),
                )
                row = cursor.fetchone()
                return self._row_to_record(row)
        except Exception:
            return None
        finally:
            connection.close()

    def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        if not self.ensure_ready():
            return []

        connection = self._connect()
        if connection is None:
            return []

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT project_id, user_id, user_email, project_name, continent_id, project_type,
                        infrastructure_type, location_label, recommended_option, assessment_payload,
                        text_planning_payload, latest_report_payload, created_at, updated_at
                    FROM {self._table_name}
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (user_id,),
                )
                return [record for row in cursor.fetchall() if (record := self._row_to_record(row)) is not None]
        except Exception:
            return []
        finally:
            connection.close()

    def get_project(self, user_id: str, project_id: str) -> dict[str, Any] | None:
        if not self.ensure_ready():
            return None

        connection = self._connect()
        if connection is None:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT project_id, user_id, user_email, project_name, continent_id, project_type,
                        infrastructure_type, location_label, recommended_option, assessment_payload,
                        text_planning_payload, latest_report_payload, created_at, updated_at
                    FROM {self._table_name}
                    WHERE user_id = %s AND project_id = %s
                    """,
                    (user_id, project_id),
                )
                return self._row_to_record(cursor.fetchone())
        except Exception:
            return None
        finally:
            connection.close()

    def update_report(self, user_id: str, project_id: str, report_payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.ensure_ready():
            return None

        connection = self._connect()
        if connection is None:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {self._table_name}
                    SET latest_report_payload = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND project_id = %s
                    RETURNING project_id, user_id, user_email, project_name, continent_id, project_type,
                        infrastructure_type, location_label, recommended_option, assessment_payload,
                        text_planning_payload, latest_report_payload, created_at, updated_at
                    """,
                    (json.dumps(report_payload), user_id, project_id),
                )
                return self._row_to_record(cursor.fetchone())
        except Exception:
            return None
        finally:
            connection.close()

    def _row_to_record(self, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "project_id": row[0],
            "user_id": row[1],
            "user_email": row[2],
            "project_name": row[3],
            "continent_id": row[4],
            "project_type": row[5],
            "infrastructure_type": row[6],
            "location_label": row[7],
            "recommended_option": row[8],
            "assessment_payload": row[9],
            "text_planning_payload": row[10] or {},
            "latest_report_payload": row[11] or {},
            "created_at": row[12].isoformat(),
            "updated_at": row[13].isoformat(),
        }
