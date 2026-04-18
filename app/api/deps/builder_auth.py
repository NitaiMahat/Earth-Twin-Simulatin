from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.domain.builder import BuilderIdentity
from app.services.builder_auth_service import builder_auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def require_builder_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> BuilderIdentity:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing builder authorization token.",
        )

    try:
        return builder_auth_service.require_builder(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
