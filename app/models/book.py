"""books 表模型。

你要手写的字段：
- id
- user_id（外键 users.id）
- title
- cover_image
- created_at

你要手写的关系：
- user: 多对一
- images: 一对多
- stories: 一对多
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

# TODO: 定义 Book 模型
class Book(Base):
    __tablename__ = "books"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    title: str = Column(String(100), nullable=False)
    cover_image: str = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    # 定义与 User 模型的多对一关系
    user = relationship("User", back_populates="books")
    # 定义与 BookImage 模型的一对多关系
    images = relationship("BookImage", back_populates="book", cascade="all, delete-orphan")
    # 定义与 Story 模型的一对多关系
    stories = relationship("Story", back_populates="book", cascade="all, delete-orphan")

