"""
数据库连接与 Session 管理模块。

你在这个文件要完成 4 件事：
1. 导入数据库相关依赖
2. 根据配置创建 engine
3. 创建 SessionLocal（会话工厂）
4. 提供 get_db() 给 FastAPI 路由使用
"""

# TODO: 导入 Generator（用于 get_db 的类型标注）
from collections.abc import AsyncGenerator

# TODO: 导入 create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# TODO: 导入 settings（读取 settings.database_url）
from app.core.config import settings


#创建异步引擎
engine = create_async_engine(settings.database_url, echo=False)


#创建异步会话工厂
SessionLocal = async_sessionmaker(
    bind=engine,# 绑定引擎
    class_=AsyncSession,# 使用异步会话
    autoflush=False,# 不自动刷新
    autocommit=False,# 不自动提交
    expire_on_commit=False,# 提交后不失效对象
)


#异步数据库会话生成器
async def get_db():
    '''异步生成器函数，提供数据库会话'''
    
    # TODO: 写会话创建、yield、关闭逻辑
    
    async with SessionLocal() as db:
        yield db
