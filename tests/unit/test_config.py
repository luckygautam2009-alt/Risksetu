import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_local_settings_initializes_with_defaults() -> None:
    """Local development environment allows default dev secrets."""
    settings = Settings(
        app_env="local",
        jwt_secret_key="CHANGE_ME_IN_ENV_FILE_NEVER_COMMIT_REAL_SECRET",
    )
    assert settings.app_env == "local"
    assert not settings.is_production


def test_production_rejects_placeholder_secret() -> None:
    """Production environment must reject placeholder secret keys."""
    with pytest.raises(ValidationError, match="Insecure JWT secret key detected"):
        Settings(
            app_env="production",
            jwt_secret_key="CHANGE_ME_IN_ENV_FILE_NEVER_COMMIT_REAL_SECRET",
            cors_allow_origins=["https://risksetu.gov.in"],
        )


def test_production_rejects_short_secret() -> None:
    """Production environment must reject secrets under 32 characters."""
    with pytest.raises(ValidationError, match="JWT secret key is too short"):
        Settings(
            app_env="production",
            jwt_secret_key="too-short-production-key-12345",
            cors_allow_origins=["https://risksetu.gov.in"],
        )



def test_production_rejects_predictable_words() -> None:
    """Production rejects keys containing words like admin, password, or secret."""
    with pytest.raises(ValidationError, match="Insecure JWT secret key detected"):
        Settings(
            app_env="production",
            jwt_secret_key="super-admin-master-production-key-99999",
            cors_allow_origins=["https://risksetu.gov.in"],
        )


def test_production_rejects_wildcard_cors() -> None:
    """Production must never allow wildcard CORS origins."""
    secure_key = "a" * 32
    with pytest.raises(ValidationError, match="Wildcard CORS origin .* is strictly forbidden"):
        Settings(
            app_env="production",
            jwt_secret_key=secure_key,
            cors_allow_origins=["*"],
        )


def test_production_accepts_valid_strong_configuration() -> None:
    """Production boots successfully with valid 32+ char random key and explicit origins."""
    strong_key = "b4f3a7d189c2e061849a1d2f8e0b6c4a51e9f0d2c3b4a5e6f708192a3b4c5d6e"
    settings = Settings(
        app_env="production",
        jwt_secret_key=strong_key,
        cors_allow_origins=["https://risksetu.gov.in"],
    )
    assert settings.is_production
    assert settings.jwt_secret_key == strong_key


def test_settings_repr_masks_secrets() -> None:
    """Printing or logging Settings object must never reveal secrets."""
    settings = Settings(
        app_env="local",
        jwt_secret_key="my_super_secret_local_value",
    )
    repr_str = repr(settings)
    assert "my_super_secret_local_value" not in repr_str
    assert "***REDACTED***" in repr_str
