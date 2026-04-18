"""应用配置管理。"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一管理环境变量配置。"""

    app_name: str = Field(default="AI绘本故事生成系统", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    # 默认用 SQLite 异步驱动，便于本地快速跑通
    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_picturebook.db",
        validation_alias="DATABASE_URL",
    )
    redis_enabled: bool = Field(default=False, validation_alias="REDIS_ENABLED")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", validation_alias="REDIS_URL")

    secret_key: str = Field(default="please_change_me", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
