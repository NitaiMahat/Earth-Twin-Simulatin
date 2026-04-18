from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.domain.auth import AuthenticatedUser

_bearer_scheme = HTTPBearer(auto_error=False)


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _decode_supabase_token(token: str) -> dict[str, Any]:
    secret = settings.supabase_jwt_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET is not configured on the backend.",
        )

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase access token format.",
        ) from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_segment)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase access token.",
        )

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token payload could not be decoded.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token payload is invalid.",
        )

    expires_at = payload.get("exp")
    if isinstance(expires_at, (int, float)) and float(expires_at) <= time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase access token.",
        )

    expected_audience = settings.supabase_jwt_audience.strip()
    if expected_audience:
        audience = payload.get("aud")
        if isinstance(audience, list):
            if expected_audience not in audience:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Supabase access token audience is invalid.",
                )
        elif audience != expected_audience:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase access token audience is invalid.",
            )

    expected_issuer = settings.supabase_jwt_issuer.strip()
    if expected_issuer:
        issuer = payload.get("iss")
        if issuer != expected_issuer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase access token issuer is invalid.",
            )

    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    payload = _decode_supabase_token(credentials.credentials)
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase token is missing a valid user id.",
        )

    app_metadata = payload.get("app_metadata", {})
    org_id = app_metadata.get("org_id") if isinstance(app_metadata, dict) else None
    role = payload.get("role")
    email = payload.get("email")

    return AuthenticatedUser(
        user_id=user_id,
        email=email if isinstance(email, str) and email.strip() else None,
        role=role if isinstance(role, str) and role.strip() else "authenticated",
        org_id=org_id if isinstance(org_id, str) and org_id.strip() else None,
    )
