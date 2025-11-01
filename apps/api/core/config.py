from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration read from environment variables."""

    app_name: str = Field(default="Aura API")
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(levelname)s %(name)s %(message)s")

    # RBAC configuration
    default_roles: tuple[str, ...] = Field(default=("viewer",))

    # Database configuration
    postgres_dsn: str = Field(default="postgresql://postgres:postgres@localhost:5432/postgres")
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="aura-documents")
    qdrant_vector_size: int = Field(default=384)
    qdrant_distance: str = Field(default="cosine")
    qdrant_on_disk_payload: bool = Field(default=True)

    # Observability configuration
    otel_enabled: bool = Field(default=False)
    otel_service_name: str = Field(default="aura-api")
    otel_exporter_otlp_endpoint: str | None = Field(default=None)
    otel_exporter_otlp_headers: str | None = Field(default=None)

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""

    return Settings()
