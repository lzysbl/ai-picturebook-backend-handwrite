"""users 表模型。

你要手写的字段：
- id
- username（唯一索引）
- password_hash
- created_at

你要手写的关系：
- books: 一对多
- stories: 一对多
"""
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base

# TODO: 定义 User 模型
class User(Base):
    __tablename__ = "users"
    id:int = Column(Integer,primary_key=True,index= True)
    username:str = Column(String(50),unique=True,index=True)
    password_hash:str = Column(String(128))
    created_at = Column(DateTime, default=func.now())#自动设置创建时间
    # 定义与 Book 模型的一对多关系
    books = relationship("Book", back_populates="user",cascade="all, delete-orphan")
    # 定义与 Story 模型的一对多关系
    stories = relationship("Story", back_populates="user",cascade="all, delete-orphan")
    


