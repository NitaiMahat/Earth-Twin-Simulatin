import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from app.api.deps import supabase_auth
from app.api.deps.supabase_auth import _decode_supabase_token


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def _sign_es256_token(private_key: ec.EllipticCurvePrivateKey, header: dict, payload: dict) -> str:
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    der_signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_signature)
    raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{header_segment}.{payload_segment}.{_b64url_encode(raw_signature)}"


def test_decode_supabase_token_accepts_es256_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    header = {"alg": "ES256", "typ": "JWT", "kid": "test-key"}
    payload = {
        "sub": "user-123",
        "aud": "authenticated",
        "role": "authenticated",
        "email": "planner@example.com",
        "app_metadata": {"org_id": "org-1"},
        "exp": int(time.time()) + 3600,
    }
    token = _sign_es256_token(private_key, header, payload)

    monkeypatch.setattr(
        supabase_auth,
        "_find_jwk",
        lambda kid: {
            "kid": kid,
            "kty": "EC",
            "crv": "P-256",
            "x": _b64url_encode(public_numbers.x.to_bytes(32, "big")),
            "y": _b64url_encode(public_numbers.y.to_bytes(32, "big")),
        },
    )

    decoded = _decode_supabase_token(token)

    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "planner@example.com"
    assert decoded["app_metadata"]["org_id"] == "org-1"


def test_decode_supabase_token_rejects_unknown_jwks_key(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = _sign_es256_token(
        private_key,
        {"alg": "ES256", "typ": "JWT", "kid": "missing-key"},
        {
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
    )

    def _raise_missing_key(kid: str) -> dict:
        raise supabase_auth.HTTPException(status_code=401, detail="Supabase access token signing key was not recognized.")

    monkeypatch.setattr(supabase_auth, "_find_jwk", _raise_missing_key)

    with pytest.raises(supabase_auth.HTTPException) as exc:
        _decode_supabase_token(token)

    assert exc.value.status_code == 401
