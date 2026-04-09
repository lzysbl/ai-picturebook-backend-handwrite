"""配置管理文件。

你要开发的内容：
1. 定义 Settings 类（继承 BaseSettings）。
2. 写字段：app_name、app_env、debug、database_url、redis_url、secret_key 等。
3. 配置 env_file='.env'。
4. 在文件末尾创建 `settings = Settings()`。

为什么先写这个：
- 后面 db、router、service 都会依赖 settings。
"""

# TODO: from pydantic import Field
from pydantic import Field
# TODO: from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

# TODO: 定义 Settings 类
class Settings(BaseSettings):
    """应用配置类。"""
   
    app_name: str = Field("AI绘本故事生成网站",validation_alias="APP_NAME", description="应用名称")
    app_env: str = Field("development",validation_alias="APP_ENV", description="应用环境")
    debug: bool = Field(False,validation_alias="APP_DEBUG", description="调试模式")# 默认值为 False
    database_url: str = Field(..., validation_alias="DATABASE_URL", description="数据库 URL")
    redis_enabled: bool = Field(False, validation_alias="REDIS_ENABLED", description="是否启用 Redis")  # 是否启用 Redis
    redis_url: str = Field(..., validation_alias="REDIS_URL", description="Redis URL")
    story_cache_ttl_seconds: int = Field(default=1800, validation_alias="STORY_CACHE_TTL_SECONDS", description="故事缓存的 TTL（秒）")  # 故事缓存的 TTL，默认值为 3600 秒
    secret_key: str = Field(..., validation_alias="SECRET_KEY", description="密钥")
    access_token_expire_minutes: int = Field(default=120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES", description="访问令牌过期时间（分钟）")  # 访问令牌过期时间，默认值为 60 分钟
    upload_dir: str = Field(default="./uploads", validation_alias="UPLOAD_DIR", description="上传文件目录")  # 上传文件目录，默认值为 ./uploads
    model_config = SettingsConfigDict(
         env_file='././.env',# 指定 .env 文件路径
         env_file_encoding='utf-8',# 指定 .env 文件编码
         extra='ignore'# 忽略 .env 文件中未定义的字段
         )  # 指定 .env 文件
# TODO: 实例化 settings
settings = Settings()