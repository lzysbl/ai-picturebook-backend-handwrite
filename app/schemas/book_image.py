"""绘本图片模块响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BookImageInfo(BaseModel):
    """绘本图片信息。"""

    id: int
    book_id: int
    image_path: str
    image_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
