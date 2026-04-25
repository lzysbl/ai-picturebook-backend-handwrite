"""应用配置管理。"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一管理环境变量配置。"""

    app_name: str = Field(default="AI绘本故事生成系统", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    # 数据库配置
    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_story.db",
        validation_alias="DATABASE_URL",
    )

    # 缓存配置（可选）
    redis_enabled: bool = Field(default=False, validation_alias="REDIS_ENABLED")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", validation_alias="REDIS_URL")
    story_cache_ttl_seconds: int = Field(default=1800, validation_alias="STORY_CACHE_TTL_SECONDS")
    quality_cache_ttl_seconds: int = Field(default=604800, validation_alias="QUALITY_CACHE_TTL_SECONDS")

    # 限流配置
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

    # 认证配置
    secret_key: str = Field(default="please_change_me", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # 文件上传
    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR")

    # AI 配置
    ai_provider: str = Field(default="mock", validation_alias="AI_PROVIDER")
    qwen_model: str = Field(default="qwen3.6-flash", validation_alias="QWEN_MODEL")
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="QWEN_BASE_URL",
    )
    qwen_api_key: str = Field(default="", validation_alias="QWEN_API_KEY")

    # 评估模型配置（LLM-as-a-Judge）
    judge_enabled: bool = Field(default=False, validation_alias="JUDGE_ENABLED")
    judge_model: str = Field(default="qwen3.6-plus", validation_alias="JUDGE_MODEL")
    judge_samples: int = Field(default=3, validation_alias="JUDGE_SAMPLES")

    # 日志配置
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
