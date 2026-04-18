from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str | None = None
    role: str = "authenticated"
    org_id: str | None = None
