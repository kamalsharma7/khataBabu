from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional, Union

from pydantic import Field, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration is loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "KhataBabu API"
    app_env: Literal["local", "development", "staging", "production"] = "local"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
    )

    log_level: str = "INFO"
    log_json: bool = False
    log_request_id_header: str = "X-Request-ID"

    database_url: Optional[str] = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "khatababu"
    postgres_password: str = "khatababu"
    postgres_db: str = "khatababu"
    postgres_ssl_mode: str = "prefer"

    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_client_id: str = "khatababu-api"
    kafka_security_protocol: str = "PLAINTEXT"

    platform_jwt_secret: str = Field(
        default="change-me-in-production-use-long-random-secret",
        min_length=32,
    )
    platform_jwt_algorithm: str = "HS256"
    platform_jwt_audience: str = "khatababu-platform"
    platform_access_token_expire_minutes: int = 60
    platform_login_session_expire_minutes: int = 10
    platform_otp_expire_seconds: int = 300
    platform_otp_length: int = 6
    platform_otp_max_attempts: int = 5
    platform_otp_pepper: str = Field(
        default="change-me-platform-otp-pepper",
        min_length=16,
    )
    platform_max_password_attempts: int = 5
    platform_lockout_minutes: int = 15
    # Local/dev only: return OTP in API response (never enable in production).
    platform_expose_otp_in_response: bool = False

    owner_jwt_secret: str = Field(
        default="change-me-owner-jwt-secret-min-32-chars-long",
        min_length=32,
    )
    owner_jwt_algorithm: str = "HS256"
    owner_jwt_audience: str = "khatababu-owner"
    owner_access_token_expire_minutes: int = 1440  # 24 hours

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, list[str]]) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                import json

                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        dsn = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )
        return str(dsn)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri_sync(self) -> str:
        """Sync URL for Alembic and other sync tools."""
        uri = self.sqlalchemy_database_uri
        return uri.replace("postgresql+asyncpg://", "postgresql://", 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def platform_otp_debug_allowed(self) -> bool:
        return self.platform_expose_otp_in_response and not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
