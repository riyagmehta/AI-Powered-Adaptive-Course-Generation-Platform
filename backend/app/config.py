from pathlib import Path

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

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # OpenAI
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4"
    openai_embedding_model: str = "text-embedding-ada-002"

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = ""
    pinecone_index_name: str = "course-platform"


settings = Settings()
