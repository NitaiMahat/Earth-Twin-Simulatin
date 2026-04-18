from __future__ import annotations

from app.models.domain.builder import BuilderIdentity, BuilderRole
from app.repositories.builder_auth_repository import builder_auth_repository


class BuilderAuthService:
    def validate_token(self, token: str) -> BuilderIdentity:
        identity = builder_auth_repository.get_identity_by_token(token)
        if identity is None:
            raise ValueError("Invalid builder token.")
        return identity

    def require_builder(self, token: str) -> BuilderIdentity:
        identity = self.validate_token(token)
        if identity.role != BuilderRole.BUILDER:
            raise PermissionError("Builder access is required for this route.")
        return identity


builder_auth_service = BuilderAuthService()
