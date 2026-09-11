from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "course_platform"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/course_platform"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Managed Postgres providers (Railway, Heroku, Render, ...) hand out a
        plain `postgres://` or `postgresql://` URL. We need the asyncpg driver
        variant, so normalize it here rather than asking every deploy target
        to know that detail."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS — comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # OpenAI
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = ""
    pinecone_index_name: str = "course-platform"

    # Doubt resolver
    doubt_cache_ttl_seconds: int = 3600
    doubt_retrieval_top_k: int = 5


settings = Settings()
