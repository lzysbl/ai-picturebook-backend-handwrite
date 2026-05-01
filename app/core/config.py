"""Application settings."""

from __future__ import annotations

from pydantic import Field, field_validator
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
    live_ai_provider: str | None = Field(default=None, validation_alias="LIVE_AI_PROVIDER")
    qwen_model: str = Field(default="qwen3.6-flash", validation_alias="QWEN_MODEL")
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="QWEN_BASE_URL",
    )
    qwen_api_key: str = Field(default="", validation_alias="QWEN_API_KEY")
    doubao_model: str = Field(default="doubao-seed-2-0-mini-260215", validation_alias="DOUBAO_MODEL")
    doubao_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        validation_alias="DOUBAO_BASE_URL",
    )
    doubao_api_key: str = Field(default="", validation_alias="DOUBAO_API_KEY")

    tts_provider: str = Field(default="none", validation_alias="TTS_PROVIDER")
    tts_max_chars: int = Field(default=420, validation_alias="TTS_MAX_CHARS")
    edge_tts_voice: str = Field(default="zh-CN-XiaoxiaoNeural", validation_alias="EDGE_TTS_VOICE")
    edge_tts_rate: str = Field(default="+0%", validation_alias="EDGE_TTS_RATE")
    edge_tts_volume: str = Field(default="+0%", validation_alias="EDGE_TTS_VOLUME")
    piper_binary: str = Field(default="piper", validation_alias="PIPER_BINARY")
    piper_model_path: str = Field(default="", validation_alias="PIPER_MODEL_PATH")
    piper_config_path: str = Field(default="", validation_alias="PIPER_CONFIG_PATH")
    piper_speaker: int | None = Field(default=None, validation_alias="PIPER_SPEAKER")
    piper_length_scale: float | None = Field(default=None, validation_alias="PIPER_LENGTH_SCALE")
    piper_noise_scale: float | None = Field(default=None, validation_alias="PIPER_NOISE_SCALE")
    piper_noise_w: float | None = Field(default=None, validation_alias="PIPER_NOISE_W")
    piper_sentence_silence: float | None = Field(default=None, validation_alias="PIPER_SENTENCE_SILENCE")
    piper_use_cuda: bool = Field(default=False, validation_alias="PIPER_USE_CUDA")

    @field_validator(
        "piper_speaker",
        "piper_length_scale",
        "piper_noise_scale",
        "piper_noise_w",
        "piper_sentence_silence",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
            return None
        if isinstance(value, str) and not value.strip().replace(".", "", 1).isdigit():
            return None
        return value

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
