"""健康检查路由。

本模块用于部署后的服务探活：
- /health：只检查 Web 服务是否能响应，适合负载均衡探活。
- /health/ready：检查数据库、Redis 等依赖是否可用，适合部署排障。
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.redis_client import get_redis
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=ApiResponse)
async def health_check() -> ApiResponse:
    """返回服务基础健康状态。"""

    return ApiResponse(
        success=True,
        message="服务正常",
        data={
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        },
    )


@router.get("/health/ready", response_model=ApiResponse)
async def readiness_check() -> ApiResponse:
    """检查数据库和 Redis 等运行依赖是否可用。"""

    checks: dict[str, dict[str, str]] = {}

    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"status": "error", "message": str(exc)}

    if settings.redis_enabled:
        try:
            redis_client = await get_redis()
            if redis_client is None:
                checks["redis"] = {"status": "degraded", "message": "Redis 未连接，系统已降级"}
            else:
                await redis_client.ping()
                checks["redis"] = {"status": "ok"}
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = {"status": "error", "message": str(exc)}
    else:
        checks["redis"] = {"status": "disabled"}

    is_ready = checks["database"]["status"] == "ok" and checks["redis"]["status"] in {"ok", "disabled", "degraded"}
    return ApiResponse(
        success=is_ready,
        message="服务依赖检查完成" if is_ready else "服务依赖异常",
        data={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        },
    )
