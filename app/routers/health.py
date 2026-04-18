"""健康检查路由。"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=ApiResponse)
async def health_check() -> ApiResponse:
    """返回服务健康状态。"""

    return ApiResponse(success=True, message="服务正常", data={"status": "ok"})
