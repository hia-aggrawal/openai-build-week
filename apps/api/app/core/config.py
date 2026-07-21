from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["mock", "openai"]
ProcessingMode = Literal["mock", "celery"]
DEVELOPMENT_SECRET_KEY = "development-only-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:3000"
    secret_key: SecretStr = SecretStr(DEVELOPMENT_SECRET_KEY)
    video_link_ttl_seconds: int = 4 * 60 * 60
    session_ttl_seconds: int = 7 * 24 * 60 * 60
    session_cookie_domain: str | None = None
    database_url: str = "sqlite:///./studyflow.db"
    redis_url: str = "redis://localhost:6379/0"
    media_storage_path: Path = Path("./media")
    processing_mode: ProcessingMode = "mock"
    openai_api_key: SecretStr | None = None
    transcription_provider: ProviderName = "mock"
    classification_provider: ProviderName = "mock"
    transcription_model: str = "gpt-4o-transcribe"
    classification_model: str = "gpt-5.4-mini"
    max_upload_size_mb: int = 500
    max_video_duration_minutes: int = 240
    min_playback_rate: float = 1.0
    max_playback_rate: float = 2.0
    mock_stage_delay_seconds: float = 0.35

    @field_validator("session_cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def require_openai_key_for_openai_providers(self) -> "Settings":
        if self.session_ttl_seconds <= 0:
            raise ValueError("SESSION_TTL_SECONDS must be positive.")
        uses_openai = (
            self.transcription_provider == "openai" or self.classification_provider == "openai"
        )
        if uses_openai and self.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when an OpenAI provider is selected.")
        if (
            self.app_env == "production"
            and self.secret_key.get_secret_value() == DEVELOPMENT_SECRET_KEY
        ):
            raise ValueError("SECRET_KEY must be set to a private value in production.")
        return self


settings = Settings()
