"""通用响应模型（所有接口统一返回结构）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """统一响应体：success + message + data。"""

    success: bool = Field(..., description="接口是否成功")
    message: str = Field(..., description="提示信息")
    data: Any | None = Field(default=None, description="响应数据")
