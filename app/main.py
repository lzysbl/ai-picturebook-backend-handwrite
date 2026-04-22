"""FastAPI 应用入口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.init_db import init_db
from app.routers import books, health, images, stories, users

app = FastAPI(
    title=settings.app_name,
    description="AI 绘本故事生成系统后端接口",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = Path(settings.upload_dir).resolve()

# 挂载静态资源目录（前端 JS/CSS）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 挂载上传文件目录（用于页面展示上传后的图片）
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时初始化数据库表。"""

    await init_db()


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    """默认跳转到登录页。"""

    return RedirectResponse(url="/ui/login")


@app.get("/ui", include_in_schema=False)
async def ui_redirect() -> RedirectResponse:
    """统一 UI 入口，跳转到登录页。"""

    return RedirectResponse(url="/ui/login")


@app.get("/ui/login", include_in_schema=False)
async def ui_login_page() -> FileResponse:
    """登录页。"""

    return FileResponse(STATIC_DIR / "login.html")


@app.get("/ui/register", include_in_schema=False)
async def ui_register_page() -> FileResponse:
    """注册页。"""

    return FileResponse(STATIC_DIR / "register.html")


@app.get("/ui/dashboard", include_in_schema=False)
async def ui_dashboard_page() -> RedirectResponse:
    """兼容旧链接：工作台入口重定向到绘本管理页。"""

    return RedirectResponse(url="/ui/books")


@app.get("/ui/books", include_in_schema=False)
async def ui_books_page() -> FileResponse:
    """绘本管理页面。"""

    return FileResponse(STATIC_DIR / "books.html")


@app.get("/ui/upload", include_in_schema=False)
async def ui_upload_page() -> FileResponse:
    """图片上传页面。"""

    return FileResponse(STATIC_DIR / "upload.html")


@app.get("/ui/generate", include_in_schema=False)
async def ui_generate_page() -> FileResponse:
    """故事生成页面。"""

    return FileResponse(STATIC_DIR / "generate.html")


@app.get("/ui/history", include_in_schema=False)
async def ui_history_page() -> FileResponse:
    """故事历史页面。"""

    return FileResponse(STATIC_DIR / "history.html")


app.include_router(health.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(images.router)
app.include_router(stories.router)
