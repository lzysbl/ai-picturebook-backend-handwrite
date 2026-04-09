"""数据库初始化（你开发的第 3 个 DB 文件）。

你要做什么：
1. 导入 Base 和 engine。
2. 导入全部模型（重要：不导入模型就不会建表）。
3. 在 init_db() 中执行 create_all。
"""

# TODO 1: 导入 Base 和 engine
from app.db.base import Base
from app.db.session import engine

async def init_db() -> None:# 初始化数据库表
    """启动时调用：初始化数据库表。"""
    
    # TODO 2: 导入全部模型，触发 metadata 注册
    # 放在函数里做延迟导入，避免你在“模型未写完”阶段被 ImportError 卡住。
    from app.models import book, book_image, story, user  # noqa: F401
    
    # TODO 3: 建表
    await  Base.metadata.create_all(bind=engine)
    
    
    
    