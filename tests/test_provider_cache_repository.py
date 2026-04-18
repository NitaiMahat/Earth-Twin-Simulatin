from app.repositories.provider_cache_repository import ProviderCacheRepository


def test_provider_cache_repository_is_disabled_without_database_url() -> None:
    repository = ProviderCacheRepository("")

    assert repository.enabled is False
    assert repository.ensure_ready() is False
    assert repository.get("missing") is None
    assert repository.set("missing", {"value": 1}, 60) is False
