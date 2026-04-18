"""数据库初始化：创建所有表。"""

from __future__ import annotations

from app.db.base import Base
from app.db.session import engine

# 导入模型，确保 SQLAlchemy 能收集所有表定义
from app.models import Book, BookImage, Story, User  # noqa: F401


async def init_db() -> None:
    """启动时建表（若表已存在则跳过）。"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
