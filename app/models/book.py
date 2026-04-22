"""绘本表 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Book(Base):
    """绘本实体：归属用户并关联多张图片与多条故事。"""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    cover_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 多对一：绘本归属某个用户
    user: Mapped["User"] = relationship(back_populates="books")
    # 一对多：绘本包含多张图片
    images: Mapped[list["BookImage"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    # 一对多：绘本对应多条故事记录
    stories: Mapped[list["Story"]] = relationship(back_populates="book", cascade="all, delete-orphan")
