"""绘本图片表 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BookImage(Base):
    """绘本图片实体：保存每一页图片路径及页码顺序。"""

    __tablename__ = "book_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    image_path: Mapped[str] = mapped_column(String(255))
    image_order: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 多对一：图片归属某本绘本
    book: Mapped["Book"] = relationship(back_populates="images")
