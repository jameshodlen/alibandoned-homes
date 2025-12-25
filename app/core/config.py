"""Application configuration using Pydantic Settings.

This module provides type-safe environment variable management
with validation and computed properties for database URIs.
"""

from functools import lru_cache
from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        APP_ENV: Application environment (development, staging, production).
        DEBUG: Enable debug mode.
        API_PREFIX: Prefix for all API routes.
        POSTGRES_USER: PostgreSQL username.
        POSTGRES_PASSWORD: PostgreSQL password.
        POSTGRES_DB: PostgreSQL database name.
        POSTGRES_HOST: PostgreSQL host address.
        POSTGRES_PORT: PostgreSQL port number.
        CORS_ORIGINS: Comma-separated list of allowed CORS origins.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "abandoned_homes"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Construct the async PostgreSQL database URI.

        Returns:
            Async database connection string for SQLAlchemy.
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def SYNC_DATABASE_URI(self) -> str:
        """Construct the sync PostgreSQL database URI for Alembic.

        Returns:
            Sync database connection string.
        """
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string.

        Returns:
            List of allowed origin URLs.
        """
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Singleton Settings instance.
    """
    return Settings()


settings = get_settings()
