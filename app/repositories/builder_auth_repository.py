from __future__ import annotations

import json

from app.core.config import settings
from app.models.domain.builder import BuilderIdentity


class BuilderAuthRepository:
    def __init__(self) -> None:
        self._identities = self._load_identities()

    def _load_identities(self) -> dict[str, BuilderIdentity]:
        with settings.builder_identities_path.open("r", encoding="utf-8") as identity_file:
            payload = json.load(identity_file)
        identities = [BuilderIdentity.model_validate(item) for item in payload]
        return {identity.token: identity for identity in identities}

    def get_identity_by_token(self, token: str) -> BuilderIdentity | None:
        return self._identities.get(token)


builder_auth_repository = BuilderAuthRepository()
