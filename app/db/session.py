"""数据库连接与异步会话管理。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 创建异步数据库引擎（echo=False 避免控制台输出过多 SQL）
engine = create_async_engine(settings.database_url, echo=False, future=True)

# 创建异步会话工厂：每次请求从这里拿一个会话对象
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：按请求提供数据库会话，并在结束后自动关闭。"""

    async with SessionLocal() as db:
        yield db
