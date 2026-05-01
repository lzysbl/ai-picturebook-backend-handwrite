"""Application settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized environment-backed settings."""

    app_name: str = Field(default="AI绘本故事生成系统", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_story.db",
        validation_alias="DATABASE_URL",
    )

    redis_enabled: bool = Field(default=False, validation_alias="REDIS_ENABLED")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", validation_alias="REDIS_URL")
    story_cache_ttl_seconds: int = Field(default=1800, validation_alias="STORY_CACHE_TTL_SECONDS")
    quality_cache_ttl_seconds: int = Field(default=604800, validation_alias="QUALITY_CACHE_TTL_SECONDS")

    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_login_limit: int = Field(default=10, validation_alias="RATE_LIMIT_LOGIN_LIMIT")
    rate_limit_login_window_seconds: int = Field(default=60, validation_alias="RATE_LIMIT_LOGIN_WINDOW_SECONDS")
    rate_limit_register_limit: int = Field(default=5, validation_alias="RATE_LIMIT_REGISTER_LIMIT")
    rate_limit_register_window_seconds: int = Field(default=300, validation_alias="RATE_LIMIT_REGISTER_WINDOW_SECONDS")
    rate_limit_story_submit_limit: int = Field(default=5, validation_alias="RATE_LIMIT_STORY_SUBMIT_LIMIT")
    rate_limit_story_submit_window_seconds: int = Field(
        default=300,
        validation_alias="RATE_LIMIT_STORY_SUBMIT_WINDOW_SECONDS",
    )

    secret_key: str = Field(default="please_change_me", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    password_reset_token_expire_minutes: int = Field(default=30, validation_alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")

    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR")

    ai_provider: str = Field(default="mock", validation_alias="AI_PROVIDER")
    qwen_model: str = Field(default="qwen3.6-flash", validation_alias="QWEN_MODEL")
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="QWEN_BASE_URL",
    )
    qwen_api_key: str = Field(default="", validation_alias="QWEN_API_KEY")

    tts_provider: str = Field(default="none", validation_alias="TTS_PROVIDER")
    tts_max_chars: int = Field(default=420, validation_alias="TTS_MAX_CHARS")
    bark_enabled: bool = Field(default=False, validation_alias="BARK_ENABLED")
    bark_voice_preset: str = Field(default="v2/en_speaker_6", validation_alias="BARK_VOICE_PRESET")
    bark_seed: int | None = Field(default=None, validation_alias="BARK_SEED")

    judge_enabled: bool = Field(default=False, validation_alias="JUDGE_ENABLED")
    judge_model: str = Field(default="qwen3.6-plus", validation_alias="JUDGE_MODEL")
    judge_samples: int = Field(default=3, validation_alias="JUDGE_SAMPLES")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_dir: str = Field(default="./logs", validation_alias="LOG_DIR")
    log_file: str = Field(default="app.log", validation_alias="LOG_FILE")
    log_max_bytes: int = Field(default=10485760, validation_alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(default=5, validation_alias="LOG_BACKUP_COUNT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
