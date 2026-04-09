"""绘本相关 Schema。"""

# TODO: 导入 datetime、BaseModel、Field
# 示例：from datetime import datetime
# 示例：from pydantic import BaseModel, Field


class BookCreateRequest:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - title: str
    - cover_image: str | None = None
    """


class BookInfo:
    """
    TODO: 改成 BaseModel 并补字段。

    建议字段：
    - id: int
    - user_id: int
    - title: str
    - cover_image: str | None
    - created_at: datetime
    """
