"""健康检查接口测试。

覆盖范围：
- 构造最小 FastAPI 应用，验证 `/health` 可以返回服务正常状态。

关联页面/模块：
- 部署验收和启动检查。
- `app/routers/health.py`

运行方式：
- `pytest tests/test_health.py`
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.health import router as health_router


def create_test_app() -> FastAPI:
    """Create a minimal app for testing health routes without external services."""
    app = FastAPI()
    app.include_router(health_router)
    return app


def test_health_check_returns_ok() -> None:
    """The basic health endpoint should respond without touching DB or Redis."""
    client = TestClient(create_test_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
