"""
Centralized application configuration.

Constitution rule #1 (server is source of truth) and rule #5 (derived data is
versioned) both start here: nothing environment- or deployment-specific is
hardcoded elsewhere in the codebase. Every later phase (auth secrets, risk
engine weights, rate limits) reads from this module instead of scattering
constants across services.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_PATTERNS = {
    "change_me",
    "secret",
    "password",
    "admin",
    "default",
    "test_secret",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App identity ---
    app_name: str = "RISKSETU AI"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg2://risksetu:risksetu@localhost:5432/risksetu",
        description="PostgreSQL/PostGIS connection string.",
    )
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Auth (used from Phase 1 onward; defined here so config is centralized
    # from day one, per the "no scattered constants" rule) ---
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_ENV_FILE_NEVER_COMMIT_REAL_SECRET",
        description="Must be overridden via env in every non-local environment.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- Rate limiting defaults (tuned per-route in later phases) ---
    default_rate_limit_per_minute: int = 60

    # --- CORS ---
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- Observability ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Demo / offline mode (Constitution rule #4: external data is disposable) ---
    offline_demo_mode: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def validate_environment_safety(self) -> "Settings":
        """Validate production and staging environments have secure configurations."""
        if self.app_env in ("production", "staging"):
            secret = self.jwt_secret_key.strip()
            secret_lower = secret.lower()

            if any(pattern in secret_lower for pattern in _INSECURE_SECRET_PATTERNS):
                raise ValueError(
                    f"Insecure JWT secret key detected in {self.app_env} environment. "
                    "Placeholder and predictable secrets are strictly prohibited."
                )

            if len(secret) < 32:
                raise ValueError(
                    f"JWT secret key is too short ({len(secret)} characters) for {self.app_env}. "
                    "A minimum of 32 characters (256-bit entropy) is required."
                )

            if "*" in self.cors_allow_origins:
                raise ValueError(
                    f"Wildcard CORS origin ('*') is strictly forbidden in {self.app_env}. "
                    "Explicit trusted origins must be specified."
                )

        return self

    def __repr__(self) -> str:
        """Prevent secrets from leaking when settings instance is printed or logged."""
        attrs = []
        for k, v in self.__dict__.items():
            if "secret" in k.lower() or "password" in k.lower() or "key" in k.lower():
                attrs.append(f"{k}='***REDACTED***'")
            else:
                attrs.append(f"{k}={v!r}")
        return f"Settings({', '.join(attrs)})"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton; import this getter, not Settings() directly."""
    return Settings()

