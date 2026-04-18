from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps.supabase_auth import get_current_user
from app.models.api.responses import AuthMeResponse
from app.models.domain.auth import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthMeResponse)
def read_current_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        org_id=user.org_id,
    )
