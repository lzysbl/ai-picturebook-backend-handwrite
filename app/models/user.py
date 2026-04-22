"""用户表 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """用户实体：保存登录账号和密码哈希。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # 使用应用层默认值，兼容老表未设置 DB 默认值的情况
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 一个用户可以拥有多本绘本
    books: Mapped[list["Book"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # 一个用户可以拥有多条故事记录
    stories: Mapped[list["Story"]] = relationship(back_populates="user", cascade="all, delete-orphan")
