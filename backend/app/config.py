from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )
    database_url: str = Field(default="postgresql+psycopg://localhost/signalflow", repr=False)
    openai_api_key: SecretStr = SecretStr("")
    openai_research_model: str = "gpt-4.1"
    openai_reasoning_model: str = "gpt-4.1"
    session_secret: SecretStr = SecretStr("")
    demo_access_code: SecretStr = SecretStr("")
    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = True
    run_timeout_seconds: int = Field(180, ge=10, le=600)
    max_search_requests: int = Field(4, ge=1, le=4)
    max_sources: int = Field(12, ge=1, le=12)
    max_runs_per_session_per_day: int = Field(10, ge=1)
    global_daily_run_limit: int = Field(50, ge=1)

    @field_validator("database_url")
    @classmethod
    def select_postgresql_driver(cls, value: str) -> str:
        # Neon supplies a libpq URL. Keep credentials and TLS query parameters
        # intact while selecting the project's installed SQLAlchemy driver.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


@lru_cache
def settings():
    return Settings()
