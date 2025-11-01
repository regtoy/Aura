from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration read from environment variables."""

    app_name: str = Field(default="Aura API")
    environment: str = Field(default="development")

    # RBAC configuration
    default_roles: tuple[str, ...] = Field(default=("viewer",))

    # Database configuration
    postgres_dsn: str = Field(default="postgresql://postgres:postgres@localhost:5432/postgres")
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str | None = Field(default=None)

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""

    return Settings()
