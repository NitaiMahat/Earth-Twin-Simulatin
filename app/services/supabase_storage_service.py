from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from app.core.config import settings


class SupabaseStorageService:
    @property
    def configured(self) -> bool:
        return bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }

    def _object_url(self, storage_path: str) -> str:
        encoded_path = quote(storage_path, safe="/")
        return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{encoded_path}"

    def upload_pdf(self, *, user_id: str, project_id: str, filename: str, pdf_bytes: bytes) -> dict[str, str]:
        if not self.configured:
            raise RuntimeError("Supabase storage is not configured on the backend.")

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safe_filename = filename.replace(" ", "-")
        storage_path = f"{user_id}/{project_id}/{timestamp}-{safe_filename}"
        upload_url = self._object_url(storage_path)
        headers = {
            **self._headers(),
            "Content-Type": "application/pdf",
            "x-upsert": "true",
        }

        try:
            response = httpx.post(
                upload_url,
                content=pdf_bytes,
                headers=headers,
                timeout=20.0,
            )
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"Supabase storage upload failed: {exc}") from exc

        return {
            "storage_path": storage_path,
            "pdf_filename": safe_filename,
            "pdf_url": self.get_file_url(storage_path),
        }

    def get_file_url(self, storage_path: str) -> str:
        if not self.configured:
            raise RuntimeError("Supabase storage is not configured on the backend.")

        encoded_path = quote(storage_path, safe="/")
        base_url = settings.supabase_url.rstrip("/")
        bucket = settings.supabase_storage_bucket

        if settings.supabase_storage_public:
            return f"{base_url}/storage/v1/object/public/{bucket}/{encoded_path}"

        try:
            response = httpx.post(
                f"{base_url}/storage/v1/object/sign/{bucket}/{encoded_path}",
                json={"expiresIn": settings.supabase_storage_signed_url_ttl_seconds},
                headers={**self._headers(), "Content-Type": "application/json"},
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
            signed_path = payload.get("signedURL") or payload.get("signedUrl")
            if not isinstance(signed_path, str) or not signed_path.strip():
                raise RuntimeError("Supabase storage did not return a signed URL.")
            if signed_path.startswith("http"):
                return signed_path
            return f"{base_url}{signed_path}"
        except Exception as exc:
            raise RuntimeError(f"Supabase signed URL creation failed: {exc}") from exc


supabase_storage_service = SupabaseStorageService()
