from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_connect_timeout: int = Field(default=10, ge=1, le=60)
    db_pool_recycle: int = Field(default=1800, ge=60, le=86400)
    database_connection_mode: Literal["local", "direct", "session_pooler", "transaction_pooler"] = (
        "local"
    )
    database_sslmode: Literal["disable", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    supabase_url: str | None = None
    supabase_project_ref: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_public_key: SecretStr | None = None
    supabase_secret_key: SecretStr | None = None
    guest_cookie_secret: SecretStr | None = None
    guest_cookie_name: str = "s2r_guest"
    guest_cookie_max_age: int = Field(default=60 * 60 * 24 * 30, ge=300)
    storage_design_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    storage_receipt_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    storage_signed_url_ttl: int = Field(default=300, ge=30, le=3600)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_supabase_identity(self) -> "Settings":
        configured = (self.supabase_url, self.supabase_project_ref, self.supabase_public_key)
        if any(configured) and not all(configured):
            raise ValueError(
                "SUPABASE_URL, SUPABASE_PROJECT_REF y SUPABASE_PUBLIC_KEY se configuran juntos"
            )
        if self.supabase_url and self.supabase_project_ref:
            host = urlparse(self.supabase_url).hostname
            if host != f"{self.supabase_project_ref}.supabase.co":
                raise ValueError("SUPABASE_URL no coincide con SUPABASE_PROJECT_REF")
        if self.guest_cookie_secret and len(self.guest_cookie_secret.get_secret_value()) < 32:
            raise ValueError("GUEST_COOKIE_SECRET debe tener al menos 32 caracteres")
        if self.database_connection_mode != "local" and self.database_sslmode in {
            "disable",
            "prefer",
        }:
            raise ValueError("Las conexiones PostgreSQL remotas deben exigir TLS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
