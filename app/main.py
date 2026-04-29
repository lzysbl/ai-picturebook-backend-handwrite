"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.redis_client import close_redis, init_redis
from app.core.request_context import get_request_id, set_request_id
from app.db.init_db import init_db
from app.routers import books, health, images, stories, users
from app.schemas.common import ApiResponse

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="AI 绘本故事生成系统后端接口",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = Path(settings.upload_dir).resolve()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    set_request_id(request_id)

    start_time = time.perf_counter()
    logger.info("request.start method=%s path=%s", request.method, request.url.path)

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request.unhandled_error path=%s", request.url.path)
        raise

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.end method=%s path=%s status=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("http_exception status=%s detail=%s", exc.status_code, exc.detail)
    payload = ApiResponse(
        success=False,
        message=str(exc.detail),
        data={"request_id": get_request_id()},
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("validation_exception errors=%s", exc.errors())
    payload = ApiResponse(
        success=False,
        message="请求参数校验失败",
        data={"errors": exc.errors(), "request_id": get_request_id()},
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception error=%s", exc)
    payload = ApiResponse(
        success=False,
        message="服务器内部错误，请稍后重试",
        data={"request_id": get_request_id()},
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    await init_redis()
    logger.info("application.startup_complete")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_redis()
    logger.info("application.shutdown_complete")


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui/login")


@app.get("/ui", include_in_schema=False)
async def ui_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui/login")


@app.get("/ui/login", include_in_schema=False)
async def ui_login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/ui/register", include_in_schema=False)
async def ui_register_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "register.html")


@app.get("/ui/forgot-password", include_in_schema=False)
async def ui_forgot_password_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "forgot-password.html")


@app.get("/ui/reset-password", include_in_schema=False)
async def ui_reset_password_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "reset-password.html")


@app.get("/ui/camera", include_in_schema=False)
async def ui_camera_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "camera.html")


@app.get("/ui/dashboard", include_in_schema=False)
async def ui_dashboard_page() -> RedirectResponse:
    return RedirectResponse(url="/ui/books")


@app.get("/ui/books", include_in_schema=False)
async def ui_books_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "books.html")


@app.get("/ui/upload", include_in_schema=False)
async def ui_upload_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "upload.html")


@app.get("/ui/generate", include_in_schema=False)
async def ui_generate_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "generate.html")


@app.get("/ui/history", include_in_schema=False)
async def ui_history_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "history.html")


app.include_router(health.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(images.router)
app.include_router(stories.router)
