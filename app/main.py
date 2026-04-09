"""FastAPI 应用入口。

你要开发的内容：
1. 创建 FastAPI 实例（title/description/version）。
2. 在启动事件中调用 init_db()。
3. 注册 routers（health/users/books/images/stories）。
4. 提供一个根路由 `/`，返回欢迎信息或跳转到 `/docs`。
5. （可选）挂载前端静态目录。

完成后验证：
- `python -m uvicorn app.main:app --reload --port 8001`
- 打开 `http://127.0.0.1:8001/docs`
"""

# TODO: 按上面提示开发 import
import uvicorn
from fastapi import FastAPI
from app.db.init_db import init_db
from app.routers import health, users, books, images, stories





# TODO: 按上面提示开发 app 和路由注册

#在应用启动时初始化数据库
@app.on_event("startup")
async def on_startup():
    await init_db()

app = FastAPI(
    title="BookStory API",
    description="AI绘本故事生成网站的后端API",
    version="1.0.0"
)

# 注册路由
# app.include_router(health.router, prefix="/health", tags=["Health"])
# app.include_router(users.router, prefix="/users", tags=["Users"])
# app.include_router(books.router, prefix="/books", tags=["Books"])
# app.include_router(images.router, prefix="/images", tags=["Images"])
# app.include_router(stories.router, prefix="/stories", tags=["Stories"])

