"""绘本模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BookCreateRequest(BaseModel):
    """创建绘本请求体。"""

    title: str = Field(..., min_length=1, max_length=100, description="绘本标题")
    cover_image: str | None = Field(default=None, description="封面图片路径")


class BookInfo(BaseModel):
    """绘本信息响应体。"""

    id: int
    user_id: int
    title: str
    cover_image: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
