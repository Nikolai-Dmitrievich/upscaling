"""
Centralized configuration management using Pydantic Settings.
"""

import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.

    Defaults point to a local Redis and the bundled model so that a fresh
    clone starts with `docker-compose up` without any manual .env editing.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
    )

    host: str = "0.0.0.0"
    port: int = Field(default=5001, ge=1, le=65535)
    debug: bool = False
    secret_key: str = DEV_SECRET_KEY

    max_file_size_mb: int = Field(default=20, ge=1)
    max_image_dimension: int = Field(default=4000, ge=512)

    @property
    def max_content_length(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    allowed_extensions: set[str] = Field(default={"jpg", "png", "jpeg", "gif", "webp"})

    allowed_mime_types: set[str] = Field(
        default={"image/jpeg", "image/png", "image/gif", "image/webp"}
    )

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    edsr_model_path: str = "models/EDSR_x2.pb"

    @field_validator("edsr_model_path")
    @classmethod
    def validate_model_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("EDSR model path cannot be empty")
        return v.strip()


settings = Settings()

if settings.secret_key == DEV_SECRET_KEY:
    logger.warning(
        "SECRET_KEY is not set, using an insecure development placeholder. "
        "Set SECRET_KEY in .env before deploying."
    )

logger.info("Configuration loaded successfully.")
