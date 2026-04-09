"""通用响应模型。

你要手写的内容：
1. ApiResponse(BaseModel)
2. 字段 success/message/data
3. 所有接口统一返回这个结构
"""
from typing import Any, Optional
from pydantic import BaseModel
# TODO: 定义 ApiResponse
class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None