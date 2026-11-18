"""Runtime configuration, read from environment variables or a local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")

    database_url: str = "postgresql://ictkb:ictkb@localhost:5432/ictkb"
    kb_env: str = "production"  # production | staging
    kb_root: Path = Path(".")

    embedding_provider: str = "cohere"  # cohere | fastembed | hash
    embedding_model: str = ""  # empty selects the provider default
    embedding_dim: int = 1024
    cohere_api_key: str = ""
    min_similarity: float = 0.35
    vision_model: str = "command-a-vision-07-2025"

    require_api_key: bool = True
    admin_token: str = ""
    default_rate_limit_per_min: int = 60
    cors_origins: str = "*"

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    @property
    def root(self) -> Path:
        return self.kb_root.resolve()

    @property
    def content_dir(self) -> Path:
        return self.root / "content"

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    @property
    def schema_dir(self) -> Path:
        return self.root / "schema"

    @property
    def migrations_dir(self) -> Path:
        return self.root / "db" / "migrations"

    @property
    def incoming_dir(self) -> Path:
        return self.root / "incoming"

    @property
    def allowed_statuses(self) -> list[str]:
        """Statuses that are indexed and searchable in the current environment."""
        return ["verified"] if self.kb_env == "production" else ["verified", "draft"]

    @property
    def cloudinary_enabled(self) -> bool:
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
