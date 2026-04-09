"""book_images 表模型。

你要手写的字段：
- id
- book_id（外键 books.id）
- image_path
- image_order
- created_at

你要手写的关系：
- book: 多对一
"""

# TODO: 定义 BookImage 模型
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
class BookImage(Base):
    __tablename__ = "book_images"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    book_id: int = Column(Integer, ForeignKey("books.id"), nullable=False)
    image_path: str = Column(String(255), nullable=False)
    image_order: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    # 定义与 Book 模型的多对一关系
    book = relationship("Book", back_populates="images")
