from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Repomind"
    debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    database_url: str = "sqlite:///./storage/repomind.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440
    vector_store_dir: Path = Path("storage/vector_indexes")
    upload_dir: Path = Path("storage/uploads")
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    cors_origins: list[str] = ["*"]
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()

