"""故事记录表 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Story(Base):
    """故事实体：保存故事文本及对应的分析结果。"""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 多对一：故事属于某本绘本
    book: Mapped["Book"] = relationship(back_populates="stories")
    # 多对一：故事由某个用户生成
    user: Mapped["User"] = relationship(back_populates="stories")
