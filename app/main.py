"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.db.init_db import init_db
from app.routers import books, health, images, stories, users
from app.schemas.common import ApiResponse

app = FastAPI(
    title=settings.app_name,
    description="AI 绘本故事生成系统后端接口",
    version="1.0.0",
)


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时初始化数据库表。"""

    await init_db()


@app.get("/", response_model=ApiResponse)
async def root() -> ApiResponse:
    """根路由：返回系统欢迎信息。"""

    return ApiResponse(
        success=True,
        message="欢迎使用 AI 绘本故事生成系统",
        data={"docs_url": "/docs"},
    )


app.include_router(health.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(images.router)
app.include_router(stories.router)
