"""stories 表模型。

你要开发的字段：
- id
- book_id（外键 books.id）
- user_id（外键 users.id）
- prompt
- image_analysis
- story_content
- created_at

你要开发的关系：
- book: 多对一
- user: 多对一
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
# TODO: 定义 Story 模型
class Story(Base):
    __tablename__ = "stories"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    book_id: int = Column(Integer, ForeignKey("books.id"), nullable=False)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    prompt: str = Column(Text, nullable=False)
    image_analysis: str = Column(Text, nullable=True)
    story_content: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    # 定义与 Book 模型的多对一关系
    book = relationship("Book", back_populates="stories")
    # 定义与 User 模型的多对一关系
    user = relationship("User", back_populates="stories")