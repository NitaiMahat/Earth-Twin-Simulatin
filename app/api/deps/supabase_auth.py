from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.domain.auth import AuthenticatedUser

_bearer_scheme = HTTPBearer(auto_error=False)
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _decode_jwt_segments(token: str) -> tuple[dict[str, Any], dict[str, Any], str, bytes]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase access token format.",
        ) from exc

    try:
        header = json.loads(_b64url_decode(header_segment).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token payload could not be decoded.",
        ) from exc

    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token payload is invalid.",
        )

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    return header, payload, signature_segment, signing_input


def _verify_hs256_signature(token: str, secret: str) -> dict[str, Any]:
    _, payload, signature_segment, signing_input = _decode_jwt_segments(token)
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
    return payload


def _int_from_b64url(value: str) -> int:
    return int.from_bytes(_b64url_decode(value), byteorder="big")


def _load_jwks() -> dict[str, Any]:
    jwks_url = settings.supabase_jwks_url
    if not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWKS is unavailable because SUPABASE_URL is not configured.",
        )

    now = time.time()
    cached = _jwks_cache.get(jwks_url)
    if cached is not None and cached[0] > now:
        return cached[1]

    try:
        response = httpx.get(
            jwks_url,
            timeout=5.0,
            headers={"User-Agent": settings.public_data_user_agent},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase signing keys could not be loaded.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase signing keys response is invalid.",
        )

    _jwks_cache[jwks_url] = (now + 3600, payload)
    return payload


def _find_jwk(kid: str) -> dict[str, Any]:
    payload = _load_jwks()
    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase signing keys response is missing key data.",
        )

    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Supabase access token signing key was not recognized.",
    )


def _verify_es256_signature(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> None:
    x = jwk.get("x")
    y = jwk.get("y")
    if not isinstance(x, str) or not isinstance(y, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase EC signing key is incomplete.",
        )

    public_key = ec.EllipticCurvePublicNumbers(
        _int_from_b64url(x),
        _int_from_b64url(y),
        ec.SECP256R1(),
    ).public_key()

    if len(signature) != 64:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase access token signature.",
        )

    der_signature = encode_dss_signature(
        int.from_bytes(signature[:32], "big"),
        int.from_bytes(signature[32:], "big"),
    )

    try:
        public_key.verify(der_signature, signing_input, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase access token.",
        ) from exc


def _verify_rs256_signature(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> None:
    n = jwk.get("n")
    e = jwk.get("e")
    if not isinstance(n, str) or not isinstance(e, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase RSA signing key is incomplete.",
        )

    public_key = rsa.RSAPublicNumbers(
        _int_from_b64url(e),
        _int_from_b64url(n),
    ).public_key()

    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase access token.",
        ) from exc


def _verify_with_jwks(token: str) -> dict[str, Any]:
    header, payload, signature_segment, signing_input = _decode_jwt_segments(token)
    algorithm = header.get("alg")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token is missing a signing key id.",
        )

    jwk = _find_jwk(kid)
    signature = _b64url_decode(signature_segment)

    if algorithm == "ES256":
        _verify_es256_signature(signing_input, signature, jwk)
    elif algorithm == "RS256":
        _verify_rs256_signature(signing_input, signature, jwk)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase access token algorithm is not supported.",
        )

    return payload


def _validate_payload_claims(payload: dict[str, Any]) -> dict[str, Any]:
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

    expected_issuer = settings.resolved_supabase_jwt_issuer
    if expected_issuer:
        issuer = payload.get("iss")
        if issuer != expected_issuer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase access token issuer is invalid.",
            )

    return payload


def _decode_supabase_token(token: str) -> dict[str, Any]:
    header, _, _, _ = _decode_jwt_segments(token)
    algorithm = header.get("alg")

    if algorithm == "HS256":
        secret = settings.supabase_jwt_secret.strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SUPABASE_JWT_SECRET is not configured for legacy HS256 token verification.",
            )
        payload = _verify_hs256_signature(token, secret)
    else:
        payload = _verify_with_jwks(token)

    return _validate_payload_claims(payload)


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
